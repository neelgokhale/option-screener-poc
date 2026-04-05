"""SQLite database module for backtesting storage."""

import sqlite3
from datetime import date
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection, enable WAL mode, and create schema if needed."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    _create_schema(conn)
    return conn


def insert_snapshot(conn: sqlite3.Connection, snapshot: dict) -> int:
    """Insert a snapshot row and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO snapshots (
            snapshot_date, universe_size, qualified_stocks, trades_screened,
            market_risk_elevated, vix_level, spy_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot["snapshot_date"],
            snapshot["universe_size"],
            snapshot["qualified_stocks"],
            snapshot["trades_screened"],
            snapshot["market_risk_elevated"],
            snapshot["vix_level"],
            snapshot["spy_price"],
        ),
    )
    conn.commit()
    return cursor.lastrowid


_TRADE_COLUMNS = (
    "snapshot_id", "rank", "symbol", "expiry", "strike", "premium", "pop",
    "delta", "theta", "implied_volatility", "expected_value", "days_to_expiry",
    "support_level", "current_price", "premium_yield", "open_interest",
    "safety_score", "adjusted_score", "next_earnings",
)


def insert_trades(conn: sqlite3.Connection, snapshot_id: int, trades: list[dict]) -> None:
    """Insert trade rows linked to a snapshot."""
    placeholders = ", ".join("?" for _ in _TRADE_COLUMNS)
    columns = ", ".join(_TRADE_COLUMNS)
    conn.executemany(
        f"INSERT INTO snapshot_trades ({columns}) VALUES ({placeholders})",
        [
            tuple(snapshot_id if col == "snapshot_id" else trade.get(col)
                  for col in _TRADE_COLUMNS)
            for trade in trades
        ],
    )
    conn.commit()


def update_trade_outcome(
    conn: sqlite3.Connection,
    trade_id: int,
    outcome: str,
    settlement_price: float,
    pnl_pct: float,
) -> None:
    """Set the outcome, settlement price, and P&L for a resolved trade."""
    conn.execute(
        """
        UPDATE snapshot_trades
        SET outcome = ?, settlement_price = ?, pnl_pct = ?
        WHERE id = ?
        """,
        (outcome, settlement_price, pnl_pct, trade_id),
    )
    conn.commit()


def get_unresolved_trades(conn: sqlite3.Connection, as_of_date: date) -> list[dict]:
    """Return trades where outcome is NULL and expiry <= as_of_date."""
    rows = conn.execute(
        """
        SELECT t.*, s.snapshot_date
        FROM snapshot_trades t
        JOIN snapshots s ON t.snapshot_id = s.id
        WHERE t.outcome IS NULL AND t.expiry <= ?
        """,
        (as_of_date.isoformat(),),
    ).fetchall()
    return [dict(row) for row in rows]


def get_summary_stats(conn: sqlite3.Connection) -> dict:
    """Compute aggregate backtesting statistics from stored trades."""
    counts = conn.execute("""
        SELECT
            COUNT(*) AS total_tracked,
            SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END) AS total_resolved,
            SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) AS total_active
        FROM snapshot_trades
    """).fetchone()

    total_tracked = counts["total_tracked"]
    total_resolved = counts["total_resolved"]
    total_active = counts["total_active"]

    if total_tracked == 0:
        return {
            "total_tracked": 0,
            "total_resolved": 0,
            "total_active": 0,
            "hit_rate": None,
            "avg_return_pct": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "win_loss_ratio": None,
            "date_range_start": None,
            "date_range_end": None,
        }

    resolved_stats = conn.execute("""
        SELECT
            SUM(CASE WHEN outcome = 'OTM' THEN 1 ELSE 0 END) AS wins,
            AVG(pnl_pct) AS avg_return_pct,
            AVG(CASE WHEN outcome = 'OTM' THEN pnl_pct END) AS avg_win_pct,
            AVG(CASE WHEN outcome = 'ITM' THEN pnl_pct END) AS avg_loss_pct
        FROM snapshot_trades
        WHERE outcome IS NOT NULL
    """).fetchone()

    date_range = conn.execute("""
        SELECT MIN(snapshot_date) AS date_range_start, MAX(snapshot_date) AS date_range_end
        FROM snapshots
    """).fetchone()

    hit_rate = None
    avg_win_pct = resolved_stats["avg_win_pct"]
    avg_loss_pct = resolved_stats["avg_loss_pct"]
    win_loss_ratio = None

    if total_resolved > 0:
        hit_rate = (resolved_stats["wins"] / total_resolved) * 100

    if avg_win_pct is not None and avg_loss_pct is not None and avg_loss_pct != 0:
        win_loss_ratio = abs(avg_win_pct) / abs(avg_loss_pct)

    return {
        "total_tracked": total_tracked,
        "total_resolved": total_resolved,
        "total_active": total_active,
        "hit_rate": hit_rate,
        "avg_return_pct": resolved_stats["avg_return_pct"],
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "win_loss_ratio": win_loss_ratio,
        "date_range_start": date_range["date_range_start"],
        "date_range_end": date_range["date_range_end"],
    }


def get_trades_by_status(conn: sqlite3.Connection, status: str) -> list[dict]:
    """Return trades filtered by status: 'active', 'resolved', or 'all'."""
    base = """
        SELECT t.*, s.snapshot_date
        FROM snapshot_trades t
        JOIN snapshots s ON t.snapshot_id = s.id
    """
    if status == "active":
        rows = conn.execute(base + " WHERE t.outcome IS NULL").fetchall()
    elif status == "resolved":
        rows = conn.execute(base + " WHERE t.outcome IS NOT NULL").fetchall()
    else:
        rows = conn.execute(base).fetchall()
    return [dict(row) for row in rows]


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            universe_size INTEGER NOT NULL,
            qualified_stocks INTEGER NOT NULL,
            trades_screened INTEGER NOT NULL,
            market_risk_elevated INTEGER NOT NULL,
            vix_level REAL NOT NULL,
            spy_price REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS snapshot_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
            rank INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            expiry TEXT NOT NULL,
            strike REAL NOT NULL,
            premium REAL NOT NULL,
            pop REAL NOT NULL,
            delta REAL NOT NULL,
            theta REAL,
            implied_volatility REAL NOT NULL,
            expected_value REAL NOT NULL,
            days_to_expiry INTEGER NOT NULL,
            support_level REAL NOT NULL,
            current_price REAL NOT NULL,
            premium_yield REAL NOT NULL,
            open_interest INTEGER NOT NULL,
            safety_score REAL,
            adjusted_score REAL,
            next_earnings TEXT,
            outcome TEXT,
            settlement_price REAL,
            pnl_pct REAL
        );
    """)
