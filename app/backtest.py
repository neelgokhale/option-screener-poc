"""Walk-forward backtest harness."""

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from app.db import insert_snapshot, insert_trades
from app.engine import market_risk, options_screener, risk_filter, safety_score, universe
from app.models.market import MarketRiskStatus
from app.models.option import ScanResult, TradeOutput
from app.resolution import resolve_expired_trades

logger = logging.getLogger(__name__)


def create_backtest_run(
    conn: sqlite3.Connection,
    *,
    name: str,
    date_range_start: date,
    date_range_end: date,
    scan_frequency: str,
    strategy_params: dict,
) -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO backtest_runs (name, started_at, date_range_start, date_range_end, scan_frequency, strategy_params)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            started_at,
            date_range_start.isoformat(),
            date_range_end.isoformat(),
            scan_frequency,
            json.dumps(strategy_params),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def snapshot_exists_for_run(
    conn: sqlite3.Connection, run_id: int, snapshot_date: date
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM snapshots WHERE backtest_run_id = ? AND snapshot_date = ?",
        (run_id, snapshot_date.isoformat()),
    ).fetchone()
    return row is not None


def find_existing_run(conn: sqlite3.Connection, name: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM backtest_runs WHERE name = ?", (name,)
    ).fetchone()
    return row["id"] if row else None


def complete_backtest_run(conn: sqlite3.Connection, run_id: int) -> None:
    conn.execute(
        "UPDATE backtest_runs SET completed_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), run_id),
    )
    conn.commit()


def trade_output_to_dict(t: TradeOutput) -> dict:
    return {
        "rank": t.rank,
        "symbol": t.symbol,
        "expiry": t.expiry.isoformat(),
        "strike": t.strike,
        "premium": t.premium,
        "pop": t.pop,
        "delta": t.delta,
        "theta": t.theta,
        "implied_volatility": t.implied_volatility,
        "expected_value": t.expected_value,
        "days_to_expiry": t.days_to_expiry,
        "support_level": t.support_level,
        "current_price": t.current_price,
        "premium_yield": t.premium_yield,
        "open_interest": t.open_interest,
        "safety_score": t.safety_score,
        "adjusted_score": t.adjusted_score,
        "next_earnings": t.next_earnings.isoformat() if t.next_earnings else None,
    }


def _generate_scan_dates(start: date, end: date, frequency: str) -> list[date]:
    if frequency != "weekly":
        raise ValueError(f"Unsupported frequency: {frequency}")

    days_until_monday = (7 - start.weekday()) % 7
    current = start + timedelta(days=days_until_monday)

    dates = []
    while current < end:
        dates.append(current)
        current += timedelta(weeks=1)
    return dates


class BacktestRunner:
    def __init__(
        self,
        conn: sqlite3.Connection,
        scan_fn: Callable[[date], ScanResult],
        settlement_price_fn: Callable[[str, str], float | None],
        market_risk_fn: Callable[[date], MarketRiskStatus],
    ) -> None:
        self._conn = conn
        self._scan_fn = scan_fn
        self._settlement_price_fn = settlement_price_fn
        self._market_risk_fn = market_risk_fn

    def run(
        self,
        start: date,
        end: date,
        frequency: str,
        name: str,
    ) -> int:
        params = collect_strategy_params()
        existing_id = find_existing_run(self._conn, name)
        if existing_id is not None:
            run_id = existing_id
        else:
            run_id = create_backtest_run(
                self._conn,
                name=name,
                date_range_start=start,
                date_range_end=end,
                scan_frequency=frequency,
                strategy_params=params,
            )

        scan_dates = _generate_scan_dates(start, end, frequency)
        for scan_date in scan_dates:
            if snapshot_exists_for_run(self._conn, run_id, scan_date):
                logger.info("Skipping %s — already completed", scan_date)
                continue

            logger.info("Scanning %s", scan_date)
            scan = self._scan_fn(scan_date)
            mr = self._market_risk_fn(scan_date)

            snapshot = {
                "snapshot_date": scan_date.isoformat(),
                "universe_size": scan.universe_size,
                "qualified_stocks": scan.qualified_stocks,
                "trades_screened": scan.trades_screened,
                "market_risk_elevated": mr.risk_elevated,
                "vix_level": mr.vix_level,
                "spy_price": mr.spy_price,
                "backtest_run_id": run_id,
            }
            snapshot_id = insert_snapshot(self._conn, snapshot)

            if scan.trades:
                trade_dicts = [trade_output_to_dict(t) for t in scan.trades]
                insert_trades(self._conn, snapshot_id, trade_dicts)

            resolved = resolve_expired_trades(
                self._conn,
                self._settlement_price_fn,
                as_of_date=scan_date,
                backtest_run_id=run_id,
            )
            logger.info("Resolved %d trades on %s", resolved, scan_date)

        complete_backtest_run(self._conn, run_id)
        return run_id


def get_backtest_summary(conn: sqlite3.Connection, run_id: int) -> dict:
    total_scans = conn.execute(
        "SELECT COUNT(*) as cnt FROM snapshots WHERE backtest_run_id = ?",
        (run_id,),
    ).fetchone()["cnt"]

    trades = conn.execute(
        """SELECT t.symbol, t.expiry, t.strike, t.premium, t.outcome, t.pnl_pct,
                  t.settlement_price, s.snapshot_date
           FROM snapshot_trades t
           JOIN snapshots s ON t.snapshot_id = s.id
           WHERE s.backtest_run_id = ?""",
        (run_id,),
    ).fetchall()
    trade_dicts = [dict(t) for t in trades]

    total_trades = len(trade_dicts)
    resolved = [t for t in trade_dicts if t["outcome"] is not None]
    total_resolved = len(resolved)

    if not resolved:
        return {
            "total_scans": total_scans,
            "total_trades": total_trades,
            "total_resolved": 0,
            "win_rate": None,
            "avg_pnl_pct": None,
            "best_trade": None,
            "worst_trade": None,
        }

    wins = [t for t in resolved if t["outcome"] == "OTM"]
    win_rate = (len(wins) / total_resolved) * 100
    avg_pnl = sum(t["pnl_pct"] for t in resolved) / total_resolved

    best = max(resolved, key=lambda t: t["pnl_pct"])
    worst = min(resolved, key=lambda t: t["pnl_pct"])

    return {
        "total_scans": total_scans,
        "total_trades": total_trades,
        "total_resolved": total_resolved,
        "win_rate": win_rate,
        "avg_pnl_pct": avg_pnl,
        "best_trade": best,
        "worst_trade": worst,
    }


def get_equity_curve(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT s.snapshot_date, SUM(t.pnl_pct) as period_pnl
           FROM snapshot_trades t
           JOIN snapshots s ON t.snapshot_id = s.id
           WHERE s.backtest_run_id = ? AND t.outcome IS NOT NULL
           GROUP BY s.snapshot_date
           ORDER BY s.snapshot_date""",
        (run_id,),
    ).fetchall()

    curve = []
    cumulative = 0.0
    for row in rows:
        cumulative += row["period_pnl"]
        curve.append({
            "date": row["snapshot_date"],
            "cumulative_pnl": cumulative,
        })
    return curve


def collect_strategy_params() -> dict:
    return {
        "universe": {
            "min_market_cap": universe.MIN_MARKET_CAP,
            "min_roe": universe.MIN_ROE,
            "max_debt_to_ebitda": universe.MAX_DEBT_TO_EBITDA,
            "min_avg_volume": universe.MIN_AVG_VOLUME,
        },
        "options": {
            "min_dte": options_screener.MIN_DTE,
            "max_dte": options_screener.MAX_DTE,
            "min_delta": options_screener.MIN_DELTA,
            "max_delta": options_screener.MAX_DELTA,
            "min_pop": options_screener.MIN_POP,
            "min_premium_yield": options_screener.MIN_PREMIUM_YIELD,
            "min_open_interest": options_screener.MIN_OPEN_INTEREST,
        },
        "risk_filter": {
            "sentiment_threshold": risk_filter.SENTIMENT_THRESHOLD,
            "relevance_threshold": risk_filter.RELEVANCE_THRESHOLD,
        },
        "safety_weights": {
            "distance": safety_score.W_DISTANCE,
            "correlation": safety_score.W_CORRELATION,
            "iv_rank": safety_score.W_IV_RANK,
            "flow": safety_score.W_FLOW,
            "market": safety_score.W_MARKET,
            "sentiment": safety_score.W_SENTIMENT,
        },
        "market_risk": {
            "vix_threshold": market_risk.VIX_THRESHOLD,
        },
    }
