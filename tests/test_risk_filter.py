"""Tests for the risk filtering layer."""

from app.engine.risk_filter import (
    _has_excessive_premarket_move,
    _has_negative_news,
    apply_risk_filters,
)
from app.models.option import Headline
from app.models.stock import StockProfile
from app.providers.base import NewsProvider
from tests.conftest import MockMarketDataProvider, make_stock


class MockNewsProvider(NewsProvider):
    """Returns configurable headlines for testing."""

    def __init__(self, headlines: dict[str, list[Headline]]) -> None:
        self._headlines = headlines

    def get_recent_headlines(self, symbol: str, hours: int = 24) -> list[Headline]:
        return self._headlines.get(symbol, [])


def _headline(title: str) -> Headline:
    return Headline(title=title, source="Test", published_at="2026-03-21T10:00:00Z")


class TestPremarketFilter:
    def test_stable_passes(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=101.0)
        assert not _has_excessive_premarket_move(profile)

    def test_volatile_excluded(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=104.0)
        assert _has_excessive_premarket_move(profile)

    def test_no_premarket_passes(self) -> None:
        profile = make_stock(pre_market_price=None)
        assert not _has_excessive_premarket_move(profile)

    def test_negative_move_excluded(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=96.0)
        assert _has_excessive_premarket_move(profile)

    def test_exactly_3pct_passes(self) -> None:
        profile = make_stock(previous_close=100.0, pre_market_price=103.0)
        assert not _has_excessive_premarket_move(profile)


class TestNewsFilter:
    def test_no_news_passes(self) -> None:
        news = MockNewsProvider({})
        assert not _has_negative_news("TEST", news)

    def test_positive_news_passes(self) -> None:
        news = MockNewsProvider({
            "TEST": [_headline("Company reports strong quarterly growth")]
        })
        assert not _has_negative_news("TEST", news)

    def test_downgrade_excluded(self) -> None:
        news = MockNewsProvider({
            "TEST": [_headline("Analyst downgrades TEST to sell")]
        })
        assert _has_negative_news("TEST", news)

    def test_lawsuit_excluded(self) -> None:
        news = MockNewsProvider({
            "TEST": [_headline("Company faces major lawsuit over patent")]
        })
        assert _has_negative_news("TEST", news)

    def test_layoff_excluded(self) -> None:
        news = MockNewsProvider({
            "TEST": [_headline("TEST announces layoffs affecting 5000 workers")]
        })
        assert _has_negative_news("TEST", news)


class TestApplyRiskFilters:
    def test_all_pass(self) -> None:
        profiles = {
            "A": make_stock(symbol="A", pre_market_price=None),
            "B": make_stock(symbol="B", pre_market_price=None),
        }
        provider = MockMarketDataProvider(profiles)
        result = apply_risk_filters(["A", "B"], profiles, provider)
        assert result.passed == ["A", "B"]

    def test_premarket_excluded(self) -> None:
        profiles = {
            "GOOD": make_stock(symbol="GOOD", pre_market_price=None),
            "BAD": make_stock(symbol="BAD", previous_close=100.0, pre_market_price=105.0),
        }
        provider = MockMarketDataProvider(profiles)
        result = apply_risk_filters(["GOOD", "BAD"], profiles, provider)
        assert "GOOD" in result.passed
        assert "BAD" in result.excluded_premarket

    def test_news_excluded(self) -> None:
        profiles = {
            "GOOD": make_stock(symbol="GOOD", pre_market_price=None),
            "BAD": make_stock(symbol="BAD", pre_market_price=None),
        }
        provider = MockMarketDataProvider(profiles)
        news = MockNewsProvider({
            "BAD": [_headline("SEC investigation into BAD")]
        })
        result = apply_risk_filters(["GOOD", "BAD"], profiles, provider, news_provider=news)
        assert "GOOD" in result.passed
        assert "BAD" in result.excluded_news
