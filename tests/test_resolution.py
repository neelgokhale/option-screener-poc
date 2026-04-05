"""Tests for the expiry resolution module."""

from datetime import date

import pytest

from app.db import get_connection, insert_snapshot, insert_trades
from app.resolution import resolve_expired_trades


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    yield c
    c.close()


SAMPLE_SNAPSHOT = {
    "snapshot_date": "2026-04-01",
    "universe_size": 500,
    "qualified_stocks": 42,
    "trades_screened": 128,
    "market_risk_elevated": False,
    "vix_level": 18.5,
    "spy_price": 520.0,
}

SAMPLE_TRADE = {
    "rank": 1,
    "symbol": "AAPL",
    "expiry": "2026-04-03",
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


class TestResolveExpiredTrades:
    def test_resolves_expired_trades_with_correct_outcome(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE])

        # Mock settlement price: 210 > 200 strike → OTM
        def mock_settlement(symbol, expiry_date):
            return 210.0

        count = resolve_expired_trades(conn, mock_settlement, as_of_date=date(2026, 4, 4))
        assert count == 1

        row = conn.execute("SELECT * FROM snapshot_trades WHERE symbol = 'AAPL'").fetchone()
        assert row["outcome"] == "OTM"
        assert row["settlement_price"] == 210.0
        assert row["pnl_pct"] == pytest.approx(1.25)

    def test_skips_trade_when_settlement_price_unavailable(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE])

        def mock_settlement(symbol, expiry_date):
            return None

        count = resolve_expired_trades(conn, mock_settlement, as_of_date=date(2026, 4, 4))
        assert count == 0

        row = conn.execute("SELECT * FROM snapshot_trades WHERE symbol = 'AAPL'").fetchone()
        assert row["outcome"] is None
        assert row["settlement_price"] is None

    def test_no_expired_trades_returns_zero(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        future_trade = {**SAMPLE_TRADE, "expiry": "2026-04-20"}
        insert_trades(conn, snapshot_id, [future_trade])

        def mock_settlement(symbol, expiry_date):
            raise AssertionError("should not be called")

        count = resolve_expired_trades(conn, mock_settlement, as_of_date=date(2026, 4, 4))
        assert count == 0

    def test_already_resolved_trades_not_re_resolved(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, snapshot_id, [SAMPLE_TRADE])

        # Resolve it first
        conn.execute(
            "UPDATE snapshot_trades SET outcome = 'OTM', settlement_price = 210.0, pnl_pct = 1.25 WHERE symbol = 'AAPL'"
        )
        conn.commit()

        def mock_settlement(symbol, expiry_date):
            raise AssertionError("should not be called for already-resolved trade")

        count = resolve_expired_trades(conn, mock_settlement, as_of_date=date(2026, 4, 4))
        assert count == 0
