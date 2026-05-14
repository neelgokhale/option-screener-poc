"""Tests for the safety score calculator."""

from datetime import date

from app.engine.safety_score import (
    W_CORRELATION,
    W_DISTANCE,
    W_FLOW,
    W_IV_RANK,
    W_MARKET,
    W_SENTIMENT,
    _beta_correlation,
    _distance_from_support,
    _iv_rank_stability,
    _market_risk_score,
    _sentiment_score,
    calculate_adjusted_score,
    calculate_safety_score,
)
from app.models.market import MarketRiskStatus
from app.models.option import Headline, ScreenedTrade
from app.providers.base import NewsProvider
from tests.conftest import make_stock


class MockNewsProvider(NewsProvider):
    def __init__(self, headlines: dict[str, list[Headline]]) -> None:
        self._headlines = headlines

    def get_recent_headlines(
        self, symbol: str, hours: int = 24, *, as_of=None
    ) -> list[Headline]:
        return self._headlines.get(symbol, [])


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


class TestBetaCorrelation:
    def test_beta_0_8(self) -> None:
        profile = make_stock(beta=0.8)
        assert _beta_correlation(profile) == 0.2

    def test_beta_above_1_clamped(self) -> None:
        profile = make_stock(beta=1.5)
        assert _beta_correlation(profile) == 0.0

    def test_beta_0_gives_max_score(self) -> None:
        profile = make_stock(beta=0.0)
        assert _beta_correlation(profile) == 1.0

    def test_negative_beta_uses_abs(self) -> None:
        profile = make_stock(beta=-0.6)
        assert _beta_correlation(profile) == 0.4

    def test_none_beta_defaults_to_half(self) -> None:
        profile = make_stock(beta=None)
        assert _beta_correlation(profile) == 0.5


class TestSentimentScore:
    def _headline(self, score: float) -> Headline:
        return Headline(
            title="test",
            source="Test",
            published_at="2026-03-21T10:00:00Z",
            ticker_sentiment_score=score,
        )

    def test_positive_sentiment(self) -> None:
        news = MockNewsProvider({
            "TEST": [self._headline(0.3), self._headline(0.5)]
        })
        # avg = 0.4, score = (1 + 0.4) / 2 = 0.7
        score = _sentiment_score("TEST", news)
        assert 0.69 < score < 0.71

    def test_negative_sentiment(self) -> None:
        news = MockNewsProvider({
            "TEST": [self._headline(-0.8)]
        })
        # avg = -0.8, score = (1 + -0.8) / 2 = 0.1
        score = _sentiment_score("TEST", news)
        assert 0.09 < score < 0.11

    def test_extreme_negative_clamped_to_zero(self) -> None:
        news = MockNewsProvider({
            "TEST": [self._headline(-1.5)]
        })
        score = _sentiment_score("TEST", news)
        assert score == 0.0

    def test_no_articles_defaults_to_half(self) -> None:
        news = MockNewsProvider({})
        score = _sentiment_score("TEST", news)
        assert score == 0.5

    def test_articles_without_scores_defaults_to_half(self) -> None:
        news = MockNewsProvider({
            "TEST": [Headline(title="test", source="T", published_at="2026-01-01")]
        })
        score = _sentiment_score("TEST", news)
        assert score == 0.5


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


class TestCompositeWeights:
    def test_weights_sum_to_one(self) -> None:
        total = W_DISTANCE + W_CORRELATION + W_IV_RANK + W_FLOW + W_MARKET + W_SENTIMENT
        assert total == 1.0

    def test_no_premarket_weight_exists(self) -> None:
        import app.engine.safety_score as ss
        assert not hasattr(ss, "W_PREMARKET")

    def test_composite_uses_new_components(self) -> None:
        from tests.test_options_screener import MockOptionsProvider, _make_put
        from app.models.option import OptionsChain

        trade = _make_trade()
        profile = make_stock(symbol="TEST", beta=0.8)
        risk = MarketRiskStatus(
            vix_level=20.0, spy_price=500.0, spy_sma_20=495.0,
            spy_above_sma=True, risk_elevated=False,
        )
        expiry_str = trade.expiry.isoformat()
        chain = OptionsChain(
            symbol="TEST", expiry=trade.expiry,
            puts=[_make_put(symbol="TEST", expiry=trade.expiry)],
            calls=[_make_put(symbol="TEST", expiry=trade.expiry, strike=160.0)],
        )
        options = MockOptionsProvider({expiry_str: chain})
        news = MockNewsProvider({"TEST": []})

        result = calculate_safety_score(
            trade, profile, risk, options, news,
        )
        assert 0.0 <= result.score <= 1.0
        assert result.components.sentiment is not None
        assert result.components.sector_correlation is not None
        assert not hasattr(result.components, "pre_market_stability")


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
