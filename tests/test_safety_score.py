"""Tests for the safety score calculator."""

from datetime import date

from app.engine.safety_score import (
    _distance_from_support,
    _iv_rank_stability,
    _market_risk_score,
    _premarket_stability,
    calculate_adjusted_score,
)
from app.models.market import MarketRiskStatus
from app.models.option import ScreenedTrade
from app.models.stock import StockProfile
from tests.conftest import make_stock


def _make_trade(
    strike: float = 140.0,
    current_price: float = 150.0,
    support_level: float = 138.0,
    iv: float = 0.30,
) -> ScreenedTrade:
    return ScreenedTrade(
        symbol="TEST",
        expiry=date(2026, 4, 5),
        strike=strike,
        bid=1.40,
        ask=1.60,
        mid_price=1.50,
        delta=-0.22,
        implied_volatility=iv,
        open_interest=5000,
        volume=500,
        current_price=current_price,
        support_level=support_level,
        days_to_expiry=17,
        pop=0.78,
        premium_yield=0.20,
        expected_value=80.0,
        expected_loss=2.0,
    )


class TestDistanceFromSupport:
    def test_typical_gap(self) -> None:
        trade = _make_trade(strike=140.0, current_price=150.0)
        score = _distance_from_support(trade)
        # (150 - 140) / 150 = 0.0667
        assert 0.06 < score < 0.07

    def test_strike_at_price(self) -> None:
        trade = _make_trade(strike=150.0, current_price=150.0)
        assert _distance_from_support(trade) == 0.0

    def test_deep_otm(self) -> None:
        trade = _make_trade(strike=100.0, current_price=150.0)
        score = _distance_from_support(trade)
        # (150 - 100) / 150 = 0.333
        assert 0.33 < score < 0.34


class TestPremarketStability:
    def test_no_premarket_data(self) -> None:
        profile = make_stock(pre_market_price=None)
        assert _premarket_stability(profile) == 1.0

    def test_stable_premarket(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=100.5)
        score = _premarket_stability(profile)
        # change = 0.5%, stability = 1 - (0.005/0.03) = 0.833
        assert 0.8 < score < 0.9

    def test_volatile_premarket(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=103.0)
        score = _premarket_stability(profile)
        # change = 3%, stability = 1 - (0.03/0.03) = 0.0
        assert score == 0.0

    def test_beyond_threshold(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=105.0)
        score = _premarket_stability(profile)
        # change = 5%, clamped to 0
        assert score == 0.0


class TestIVRankStability:
    def test_low_iv_high_score(self) -> None:
        trade = _make_trade(iv=0.15)
        assert _iv_rank_stability(trade) == 1.0

    def test_high_iv_low_score(self) -> None:
        trade = _make_trade(iv=0.60)
        assert _iv_rank_stability(trade) == 0.0

    def test_mid_iv(self) -> None:
        trade = _make_trade(iv=0.375)
        score = _iv_rank_stability(trade)
        assert 0.45 < score < 0.55  # ~0.50


class TestMarketRiskScore:
    def test_calm_market(self) -> None:
        risk = MarketRiskStatus(
            vix_level=13.0, spy_price=500.0, spy_sma_20=495.0,
            spy_above_sma=True, risk_elevated=False,
        )
        score = _market_risk_score(risk)
        assert score > 0.9

    def test_stressed_market(self) -> None:
        risk = MarketRiskStatus(
            vix_level=30.0, spy_price=480.0, spy_sma_20=495.0,
            spy_above_sma=False, risk_elevated=True,
        )
        score = _market_risk_score(risk)
        assert score == 0.0

    def test_moderate_vix(self) -> None:
        risk = MarketRiskStatus(
            vix_level=21.0, spy_price=500.0, spy_sma_20=495.0,
            spy_above_sma=True, risk_elevated=False,
        )
        score = _market_risk_score(risk)
        assert 0.4 < score < 0.6  # ~0.50


class TestAdjustedScore:
    def test_safety_boosts_ev(self) -> None:
        adjusted = calculate_adjusted_score(ev=100.0, safety_score=0.5)
        assert adjusted == 150.0

    def test_zero_safety(self) -> None:
        adjusted = calculate_adjusted_score(ev=100.0, safety_score=0.0)
        assert adjusted == 100.0

    def test_max_safety(self) -> None:
        adjusted = calculate_adjusted_score(ev=100.0, safety_score=1.0)
        assert adjusted == 200.0
