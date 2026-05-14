"""Tests for the scoring module — pure functions, no DB needed."""

import pytest

from app.scoring import compute_pnl, compute_stats


class TestComputePnl:
    def test_otm_trade_returns_premium_yield(self):
        """settlement_price > strike → OTM, P&L = premium / strike × 100."""
        outcome, pnl = compute_pnl(strike=200.0, premium=2.50, settlement_price=210.0)
        assert outcome == "OTM"
        assert pnl == pytest.approx(1.25)  # 2.50 / 200 × 100

    def test_itm_trade_returns_loss_offset_by_premium(self):
        """settlement_price <= strike → ITM, P&L = ((settlement - strike) + premium) / strike × 100."""
        outcome, pnl = compute_pnl(strike=200.0, premium=2.50, settlement_price=195.0)
        assert outcome == "ITM"
        assert pnl == pytest.approx(-1.25)  # ((195 - 200) + 2.50) / 200 × 100

    def test_settlement_at_strike_is_itm(self):
        """Boundary: settlement == strike → ITM (assigned), P&L = premium / strike × 100."""
        outcome, pnl = compute_pnl(strike=200.0, premium=2.50, settlement_price=200.0)
        assert outcome == "ITM"
        assert pnl == pytest.approx(1.25)  # ((200 - 200) + 2.50) / 200 × 100


class TestComputeStats:
    def test_mixed_outcomes(self):
        trades = [
            {"outcome": "OTM", "pnl_pct": 1.25},
            {"outcome": "OTM", "pnl_pct": 0.80},
            {"outcome": "ITM", "pnl_pct": -2.50},
        ]
        stats = compute_stats(trades)
        assert stats["hit_rate"] == pytest.approx(200 / 3)  # 2 wins out of 3
        assert stats["avg_return_pct"] == pytest.approx((1.25 + 0.80 - 2.50) / 3)
        assert stats["avg_win_pct"] == pytest.approx((1.25 + 0.80) / 2)
        assert stats["avg_loss_pct"] == pytest.approx(-2.50)
        assert stats["win_loss_ratio"] == pytest.approx((1.25 + 0.80) / 2 / 2.50)

    def test_empty_list_returns_all_none(self):
        stats = compute_stats([])
        assert stats["hit_rate"] is None
        assert stats["avg_return_pct"] is None
        assert stats["avg_win_pct"] is None
        assert stats["avg_loss_pct"] is None
        assert stats["win_loss_ratio"] is None

    def test_all_wins_no_losses(self):
        trades = [
            {"outcome": "OTM", "pnl_pct": 1.25},
            {"outcome": "OTM", "pnl_pct": 0.80},
        ]
        stats = compute_stats(trades)
        assert stats["hit_rate"] == pytest.approx(100.0)
        assert stats["avg_return_pct"] == pytest.approx((1.25 + 0.80) / 2)
        assert stats["avg_win_pct"] == pytest.approx((1.25 + 0.80) / 2)
        assert stats["avg_loss_pct"] is None
        assert stats["win_loss_ratio"] is None
