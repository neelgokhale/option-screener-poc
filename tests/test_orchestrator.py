"""Tests for the backtest orchestrator."""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app.db import get_connection
from app.models.option import ScanResult, TradeOutput


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    yield c
    c.close()


def _make_trade(rank: int = 1, symbol: str = "AAPL") -> TradeOutput:
    return TradeOutput(
        rank=rank,
        symbol=symbol,
        expiry=date(2026, 4, 18),
        strike=200.0,
        premium=2.50,
        pop=0.82,
        delta=-0.18,
        theta=-0.05,
        implied_volatility=0.25,
        expected_value=1.80,
        days_to_expiry=14,
        support_level=195.0,
        current_price=215.0,
        premium_yield=0.65,
        open_interest=5000,
        safety_score=0.75,
        adjusted_score=3.15,
        next_earnings=date(2026, 5, 1),
    )


def _make_scan_result(trades: list[TradeOutput] | None = None) -> ScanResult:
    if trades is None:
        trades = [_make_trade(1, "AAPL"), _make_trade(2, "MSFT")]
    return ScanResult(
        trades=trades,
        universe_size=500,
        qualified_stocks=42,
        trades_screened=128,
        scan_timestamp="2026-04-04T14:00:00+00:00",
    )


def _mock_market_risk():
    from app.models.market import MarketRiskStatus
    return MarketRiskStatus(
        vix_level=18.5,
        vix_threshold=25.0,
        spy_price=520.0,
        spy_sma_20=515.0,
        spy_above_sma=True,
        risk_elevated=False,
        risk_reason=None,
    )


class TestSnapshotDailyTrades:
    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_persists_snapshot_and_trades(self, mock_scan, mock_risk, conn):
        mock_scan.return_value = _make_scan_result()
        mock_risk.return_value = _mock_market_risk()

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()
        snapshot_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )

        assert snapshot_id is not None

        # Verify snapshot row
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        assert row["snapshot_date"] == "2026-04-04"
        assert row["universe_size"] == 500
        assert row["qualified_stocks"] == 42
        assert row["trades_screened"] == 128

        # Verify trade rows
        trades = conn.execute(
            "SELECT * FROM snapshot_trades WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchall()
        assert len(trades) == 2
        assert trades[0]["symbol"] == "AAPL"
        assert trades[1]["symbol"] == "MSFT"

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_captures_market_context(self, mock_scan, mock_risk, conn):
        mock_scan.return_value = _make_scan_result()
        mock_risk.return_value = _mock_market_risk()

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()
        snapshot_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )

        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        assert row["vix_level"] == 18.5
        assert row["spy_price"] == 520.0
        assert row["market_risk_elevated"] == 0  # False stored as 0

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_captures_elevated_market_risk(self, mock_scan, mock_risk, conn):
        from app.models.market import MarketRiskStatus

        mock_scan.return_value = _make_scan_result()
        mock_risk.return_value = MarketRiskStatus(
            vix_level=30.0,
            vix_threshold=25.0,
            spy_price=480.0,
            spy_sma_20=500.0,
            spy_above_sma=False,
            risk_elevated=True,
            risk_reason="VIX at 30.0 (above 25.0)",
        )

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()
        snapshot_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )

        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        assert row["vix_level"] == 30.0
        assert row["spy_price"] == 480.0
        assert row["market_risk_elevated"] == 1  # True stored as 1

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_skips_if_snapshot_exists_for_today(self, mock_scan, mock_risk, conn):
        mock_scan.return_value = _make_scan_result()
        mock_risk.return_value = _mock_market_risk()

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()

        # First call succeeds
        first_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )
        assert first_id is not None

        # Second call for same date returns None
        second_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )
        assert second_id is None

        # Only one snapshot row exists
        count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        assert count == 1

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_empty_scan_persists_snapshot_but_no_trades(self, mock_scan, mock_risk, conn):
        mock_scan.return_value = _make_scan_result(trades=[])
        mock_risk.return_value = _mock_market_risk()

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()
        snapshot_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )

        assert snapshot_id is not None

        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        assert row["trades_screened"] == 128  # from ScanResult metadata
        assert row["snapshot_date"] == "2026-04-04"

        trade_count = conn.execute(
            "SELECT COUNT(*) FROM snapshot_trades WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()[0]
        assert trade_count == 0

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_trade_field_mapping(self, mock_scan, mock_risk, conn):
        trade = _make_trade(rank=1, symbol="AAPL")
        mock_scan.return_value = _make_scan_result(trades=[trade])
        mock_risk.return_value = _mock_market_risk()

        from app.orchestrator import snapshot_daily_trades

        provider = MagicMock()
        snapshot_id = snapshot_daily_trades(
            conn, provider, provider, today=date(2026, 4, 4)
        )

        row = conn.execute(
            "SELECT * FROM snapshot_trades WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()

        assert row["rank"] == 1
        assert row["symbol"] == "AAPL"
        assert row["expiry"] == "2026-04-18"
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
        # Outcome fields start as NULL
        assert row["outcome"] is None
        assert row["settlement_price"] is None
        assert row["pnl_pct"] is None
