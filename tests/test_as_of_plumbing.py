"""Tests for as_of plumbing through ABCs and engine functions."""

from datetime import date, timedelta

import pandas as pd

from app.engine.pipeline import run_scan
from app.models.option import Headline, OptionContract, OptionsChain
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, NewsProvider, OptionsDataProvider
from tests.conftest import make_stock


class AsOfTrackingMarketProvider(MarketDataProvider):
    """Tracks which as_of values were passed to each method."""

    def __init__(self, stocks: dict[str, StockProfile]) -> None:
        self._stocks = stocks
        self.as_of_calls: list[tuple[str, date | None]] = []

    def get_stock_info(
        self, symbol: str, *, as_of: date | None = None
    ) -> StockProfile | None:
        self.as_of_calls.append(("get_stock_info", as_of))
        return self._stocks.get(symbol)

    def get_price_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        *,
        as_of: date | None = None,
    ) -> pd.DataFrame:
        self.as_of_calls.append(("get_price_history", as_of))
        prices = [150 - i for i in range(10)] + [140] + [140 + i for i in range(10)]
        return pd.DataFrame({
            "Open": prices,
            "High": [p + 1 for p in prices],
            "Low": prices,
            "Close": [p + 0.5 for p in prices],
            "Volume": [1000000] * len(prices),
        })

    def get_sp500_symbols(self) -> list[str]:
        return list(self._stocks.keys())


class AsOfTrackingOptionsProvider(OptionsDataProvider):
    def __init__(self) -> None:
        self.as_of_calls: list[tuple[str, date | None]] = []

    def get_expiry_dates(
        self, symbol: str, *, as_of: date | None = None
    ) -> list[str]:
        self.as_of_calls.append(("get_expiry_dates", as_of))
        target = (as_of or date.today()) + timedelta(days=17)
        return [target.isoformat()]

    def get_options_chain(
        self, symbol: str, expiry: str, *, as_of: date | None = None
    ) -> OptionsChain:
        self.as_of_calls.append(("get_options_chain", as_of))
        expiry_date = date.fromisoformat(expiry)
        put = OptionContract(
            symbol=symbol,
            expiry=expiry_date,
            strike=135.0,
            option_type="put",
            bid=1.40,
            ask=1.60,
            last_price=1.50,
            delta=-0.22,
            theta=-0.05,
            implied_volatility=0.30,
            open_interest=5000,
            volume=500,
        )
        return OptionsChain(symbol=symbol, expiry=expiry_date, puts=[put], calls=[put])


class AsOfTrackingNewsProvider(NewsProvider):
    def __init__(self) -> None:
        self.as_of_calls: list[tuple[str, date | None]] = []

    def get_recent_headlines(
        self, symbol: str, hours: int = 24, *, as_of: date | None = None
    ) -> list[Headline]:
        self.as_of_calls.append(("get_recent_headlines", as_of))
        return []


class TestAsOfPlumbing:
    def test_run_scan_threads_as_of_through_all_providers(self) -> None:
        stock = make_stock(symbol="TEST", current_price=150.0)
        market = AsOfTrackingMarketProvider({"TEST": stock})
        options = AsOfTrackingOptionsProvider()
        news = AsOfTrackingNewsProvider()

        target_date = date(2026, 1, 5)
        run_scan(
            market_provider=market,
            options_provider=options,
            news_provider=news,
            symbols=["TEST"],
            as_of=target_date,
        )

        for method, as_of_val in market.as_of_calls:
            assert as_of_val == target_date, (
                f"MarketProvider.{method} received as_of={as_of_val}, "
                f"expected {target_date}"
            )

        for method, as_of_val in options.as_of_calls:
            assert as_of_val == target_date, (
                f"OptionsProvider.{method} received as_of={as_of_val}, "
                f"expected {target_date}"
            )

        for method, as_of_val in news.as_of_calls:
            assert as_of_val == target_date, (
                f"NewsProvider.{method} received as_of={as_of_val}, "
                f"expected {target_date}"
            )

    def test_run_scan_none_as_of_passes_none(self) -> None:
        stock = make_stock(symbol="TEST", current_price=150.0)
        market = AsOfTrackingMarketProvider({"TEST": stock})
        options = AsOfTrackingOptionsProvider()

        run_scan(
            market_provider=market,
            options_provider=options,
            symbols=["TEST"],
        )

        for method, as_of_val in market.as_of_calls:
            assert as_of_val is None, (
                f"MarketProvider.{method} received as_of={as_of_val}, expected None"
            )
