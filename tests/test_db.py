"""Tests for the database module."""

import pytest

from datetime import date

from app.db import get_connection, insert_snapshot, insert_trades, get_unresolved_trades, update_trade_outcome, get_trades_by_status, get_summary_stats


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    yield c
    c.close()


SAMPLE_SNAPSHOT = {
    "snapshot_date": "2026-04-04",
    "universe_size": 500,
    "qualified_stocks": 42,
    "trades_screened": 128,
    "market_risk_elevated": False,
    "vix_level": 18.5,
    "spy_price": 520.0,
}


class TestGetConnection:
    def test_creates_tables_and_enables_wal(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)

        # WAL mode enabled (only works with file-based DBs)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

        # snapshots table exists with expected columns
        snapshot_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(snapshots)").fetchall()
        }
        assert snapshot_cols == {
            "id",
            "snapshot_date",
            "universe_size",
            "qualified_stocks",
            "trades_screened",
            "market_risk_elevated",
            "vix_level",
            "spy_price",
        }

        # snapshot_trades table exists with expected columns
        trade_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(snapshot_trades)").fetchall()
        }
        expected_trade_cols = {
            "id",
            "snapshot_id",
            "rank",
            "symbol",
            "expiry",
            "strike",
            "premium",
            "pop",
            "delta",
            "theta",
            "implied_volatility",
            "expected_value",
            "days_to_expiry",
            "support_level",
            "current_price",
            "premium_yield",
            "open_interest",
            "safety_score",
            "adjusted_score",
            "next_earnings",
            "outcome",
            "settlement_price",
            "pnl_pct",
        }
        assert trade_cols == expected_trade_cols

        # Foreign key on snapshot_id
        fk_info = conn.execute("PRAGMA foreign_key_list(snapshot_trades)").fetchall()
        assert any(row[2] == "snapshots" and row[3] == "snapshot_id" for row in fk_info)

        conn.close()


class TestInsertSnapshot:
    def test_returns_id_and_persists_fields(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)

        assert isinstance(snapshot_id, int)
        assert snapshot_id >= 1

        row = conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        assert row["snapshot_date"] == "2026-04-04"
        assert row["universe_size"] == 500
        assert row["qualified_stocks"] == 42
        assert row["trades_screened"] == 128
        assert row["market_risk_elevated"] == 0  # SQLite stores bool as int
        assert row["vix_level"] == 18.5
        assert row["spy_price"] == 520.0


SAMPLE_TRADE = {
    "rank": 1,
    "symbol": "AAPL",
    "expiry": "2026-04-18",
    "strike": 200.0,
    "premium": 2.50,
    "pop": 0.82,
    "delta": -0.18,
    "theta": -0.05,
    "implied_volatility": 0.25,
    "expected_value": 1.80,
    "days_to_expiry": 14,
    "support_level": 195.0,
    "current_price": 215.0,
    "premium_yield": 0.65,
    "open_interest": 5000,
    "safety_score": 0.75,
    "adjusted_score": 3.15,
    "next_earnings": "2026-05-01",
}


class TestInsertTrades:
    def test_persists_all_fields_with_null_outcomes(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        trade2 = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT"}
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE, trade2])

        rows = conn.execute(
            "SELECT * FROM snapshot_trades WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchall()
        assert len(rows) == 2

        row = rows[0]
        assert row["snapshot_id"] == snapshot_id
        assert row["symbol"] == "AAPL"
        assert row["strike"] == 200.0
        assert row["premium"] == 2.50
        assert row["pop"] == 0.82
        assert row["delta"] == -0.18
        assert row["theta"] == -0.05
        assert row["implied_volatility"] == 0.25
        assert row["expected_value"] == 1.80
        assert row["days_to_expiry"] == 14
        assert row["support_level"] == 195.0
        assert row["current_price"] == 215.0
        assert row["premium_yield"] == 0.65
        assert row["open_interest"] == 5000
        assert row["safety_score"] == 0.75
        assert row["adjusted_score"] == 3.15
        assert row["next_earnings"] == "2026-05-01"
        # Outcome fields are NULL until expiry resolution
        assert row["outcome"] is None
        assert row["settlement_price"] is None
        assert row["pnl_pct"] is None


class TestGetUnresolvedTrades:
    def test_returns_expired_trades_with_null_outcome(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        expired = {**SAMPLE_TRADE, "expiry": "2026-04-01"}  # expired
        future = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2026-04-20"}  # not expired
        insert_trades(conn, snapshot_id, [expired, future])

        rows = get_unresolved_trades(conn, as_of_date=date(2026, 4, 4))
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["expiry"] == "2026-04-01"

    def test_ignores_already_resolved_trades(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        expired = {**SAMPLE_TRADE, "expiry": "2026-04-01"}
        insert_trades(conn, snapshot_id, [expired])

        # Manually resolve it
        conn.execute(
            "UPDATE snapshot_trades SET outcome = 'OTM', settlement_price = 210.0, pnl_pct = 1.25 WHERE symbol = 'AAPL'"
        )
        conn.commit()

        rows = get_unresolved_trades(conn, as_of_date=date(2026, 4, 4))
        assert len(rows) == 0


class TestUpdateTradeOutcome:
    def test_sets_outcome_fields(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE])

        trade = conn.execute("SELECT id FROM snapshot_trades").fetchone()
        update_trade_outcome(conn, trade["id"], outcome="OTM", settlement_price=210.0, pnl_pct=1.25)

        row = conn.execute("SELECT * FROM snapshot_trades WHERE id = ?", (trade["id"],)).fetchone()
        assert row["outcome"] == "OTM"
        assert row["settlement_price"] == 210.0
        assert row["pnl_pct"] == 1.25

    def test_itm_outcome(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE])

        trade = conn.execute("SELECT id FROM snapshot_trades").fetchone()
        update_trade_outcome(conn, trade["id"], outcome="ITM", settlement_price=195.0, pnl_pct=-1.25)

        row = conn.execute("SELECT * FROM snapshot_trades WHERE id = ?", (trade["id"],)).fetchone()
        assert row["outcome"] == "ITM"
        assert row["settlement_price"] == 195.0
        assert row["pnl_pct"] == -1.25


class TestGetTradesByStatus:
    def _seed_mixed_trades(self, conn):
        """Insert one resolved and one active trade, return snapshot_id."""
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        resolved = {**SAMPLE_TRADE, "expiry": "2026-04-01"}
        active = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2026-04-20"}
        insert_trades(conn, snapshot_id, [resolved, active])
        trade = conn.execute(
            "SELECT id FROM snapshot_trades WHERE symbol = 'AAPL'"
        ).fetchone()
        update_trade_outcome(conn, trade["id"], "OTM", 210.0, 1.25)
        return snapshot_id

    def test_active_returns_only_null_outcome(self, conn):
        self._seed_mixed_trades(conn)
        rows = get_trades_by_status(conn, "active")
        assert len(rows) == 1
        assert rows[0]["symbol"] == "MSFT"
        assert rows[0]["outcome"] is None

    def test_resolved_returns_only_non_null_outcome(self, conn):
        self._seed_mixed_trades(conn)
        rows = get_trades_by_status(conn, "resolved")
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["outcome"] == "OTM"

    def test_all_returns_everything(self, conn):
        self._seed_mixed_trades(conn)
        rows = get_trades_by_status(conn, "all")
        assert len(rows) == 2

    def test_includes_snapshot_date(self, conn):
        self._seed_mixed_trades(conn)
        rows = get_trades_by_status(conn, "all")
        assert all(row["snapshot_date"] == "2026-04-04" for row in rows)


class TestGetSummaryStats:
    def test_with_mixed_outcomes(self, conn):
        snap1 = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "snapshot_date": "2026-04-01"})
        snap2 = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "snapshot_date": "2026-04-04"})

        # 2 resolved trades on snap1, 1 active on snap2
        win = {**SAMPLE_TRADE, "expiry": "2026-04-01"}
        loss = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2026-04-01"}
        active = {**SAMPLE_TRADE, "rank": 3, "symbol": "GOOG", "expiry": "2026-04-20"}
        insert_trades(conn, snap1, [win, loss])
        insert_trades(conn, snap2, [active])

        # Resolve win and loss
        trades = conn.execute("SELECT id, symbol FROM snapshot_trades WHERE expiry = '2026-04-01'").fetchall()
        for t in trades:
            if t["symbol"] == "AAPL":
                update_trade_outcome(conn, t["id"], "OTM", 210.0, 1.25)
            else:
                update_trade_outcome(conn, t["id"], "ITM", 195.0, -1.25)

        stats = get_summary_stats(conn)
        assert stats["total_tracked"] == 3
        assert stats["total_resolved"] == 2
        assert stats["total_active"] == 1
        assert stats["hit_rate"] == 50.0  # 1 OTM out of 2 resolved
        assert stats["avg_return_pct"] == 0.0  # (1.25 + -1.25) / 2
        assert stats["avg_win_pct"] == 1.25
        assert stats["avg_loss_pct"] == -1.25
        assert stats["win_loss_ratio"] == 1.0  # |1.25| / |1.25|
        assert stats["date_range_start"] == "2026-04-01"
        assert stats["date_range_end"] == "2026-04-04"

    def test_empty_database(self, conn):
        stats = get_summary_stats(conn)
        assert stats["total_tracked"] == 0
        assert stats["total_resolved"] == 0
        assert stats["total_active"] == 0
        assert stats["hit_rate"] is None
        assert stats["avg_return_pct"] is None
        assert stats["avg_win_pct"] is None
        assert stats["avg_loss_pct"] is None
        assert stats["win_loss_ratio"] is None
        assert stats["date_range_start"] is None
        assert stats["date_range_end"] is None


class TestConfig:
    def test_settings_has_db_path_with_default(self):
        from app.config import Settings

        s = Settings(finnhub_api_key="test")
        assert hasattr(s, "db_path")
        assert isinstance(s.db_path, str)
        assert s.db_path.endswith(".db")
