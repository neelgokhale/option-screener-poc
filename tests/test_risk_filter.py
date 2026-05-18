"""Tests for the risk filtering layer."""

from unittest.mock import patch

from app.engine.risk_filter import (
    _has_negative_sentiment,
    apply_risk_filters,
)
from app.models.option import Headline
from app.providers.base import NewsProvider
from tests.conftest import MockMarketDataProvider, make_stock


class MockNewsProvider(NewsProvider):
    """Returns configurable headlines for testing."""

    def __init__(self, headlines: dict[str, list[Headline]]) -> None:
        self._headlines = headlines

    def get_recent_headlines(
        self, symbol: str, hours: int = 24, *, as_of=None
    ) -> list[Headline]:
        return self._headlines.get(symbol, [])


def _headline(
    title: str,
    sentiment: float | None = None,
    relevance: float | None = None,
) -> Headline:
    return Headline(
        title=title,
        source="Test",
        published_at="2026-03-21T10:00:00Z",
        ticker_sentiment_score=sentiment,
        relevance_score=relevance,
    )


class TestSentimentFilter:
    def test_negative_sentiment_excluded(self) -> None:
        """Articles with score < -0.35 AND relevance > 0.5 trigger exclusion."""
        news = MockNewsProvider({
            "TEST": [_headline("Bad news", sentiment=-0.50, relevance=0.8)]
        })
        assert _has_negative_sentiment("TEST", news)

    def test_negative_but_irrelevant_passes(self) -> None:
        """Negative sentiment with low relevance does not trigger exclusion."""
        news = MockNewsProvider({
            "TEST": [_headline("Bad news", sentiment=-0.50, relevance=0.3)]
        })
        assert not _has_negative_sentiment("TEST", news)

    def test_relevant_but_positive_passes(self) -> None:
        """High relevance with positive sentiment does not trigger exclusion."""
        news = MockNewsProvider({
            "TEST": [_headline("Good news", sentiment=0.20, relevance=0.8)]
        })
        assert not _has_negative_sentiment("TEST", news)

    def test_no_articles_passes(self) -> None:
        news = MockNewsProvider({})
        assert not _has_negative_sentiment("TEST", news)


class TestApplyRiskFilters:
    @patch("app.engine.risk_filter._has_upcoming_earnings", return_value=False)
    def test_all_pass(self, _mock_earnings) -> None:
        profiles = {
            "A": make_stock(symbol="A"),
            "B": make_stock(symbol="B"),
        }
        provider = MockMarketDataProvider(profiles)
        result = apply_risk_filters(["A", "B"], profiles, provider)
        assert result.passed == ["A", "B"]

    @patch("app.engine.risk_filter._has_upcoming_earnings", return_value=False)
    def test_big_premarket_move_no_longer_excluded(self, _mock_earnings) -> None:
        profiles = {
            "JUMPY": make_stock(symbol="JUMPY", previous_close=100.0, pre_market_price=110.0),
        }
        provider = MockMarketDataProvider(profiles)
        result = apply_risk_filters(["JUMPY"], profiles, provider)
        assert "JUMPY" in result.passed

    @patch("app.engine.risk_filter._has_upcoming_earnings", return_value=False)
    def test_sentiment_excluded(self, _mock_earnings) -> None:
        profiles = {
            "GOOD": make_stock(symbol="GOOD"),
            "BAD": make_stock(symbol="BAD"),
        }
        provider = MockMarketDataProvider(profiles)
        news = MockNewsProvider({
            "BAD": [_headline("Bad quarter", sentiment=-0.50, relevance=0.8)]
        })
        result = apply_risk_filters(["GOOD", "BAD"], profiles, provider, news_provider=news)
        assert "GOOD" in result.passed
        assert "BAD" in result.excluded_sentiment
