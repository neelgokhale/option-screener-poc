"""Shared test fixtures.

Provides mock providers with deterministic data so tests don't hit
real APIs. Each fixture returns a provider pre-loaded with sample
StockProfile data covering various filter edge cases.
"""

import pandas as pd
import pytest

from app.models.option import OptionsChain
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """In-memory provider for testing. Stocks are loaded via a dict."""

    def __init__(self, stocks: dict[str, StockProfile]) -> None:
        self._stocks = stocks

    def get_stock_info(self, symbol: str) -> StockProfile | None:
        return self._stocks.get(symbol)

    def get_price_history(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_sp500_symbols(self) -> list[str]:
        return list(self._stocks.keys())


def make_stock(
    symbol: str = "TEST",
    name: str = "Test Corp",
    sector: str = "Technology",
    market_cap: float = 50_000_000_000,
    net_income: float = 5_000_000_000,
    roe: float = 0.20,
    debt_to_ebitda: float = 1.5,
    avg_volume: float = 10_000_000,
    current_price: float = 150.0,
    previous_close: float = 149.0,
    pre_market_price: float | None = None,
) -> StockProfile:
    """Factory for creating StockProfile instances with sensible defaults."""
    return StockProfile(
        symbol=symbol,
        name=name,
        sector=sector,
        market_cap=market_cap,
        net_income=net_income,
        roe=roe,
        debt_to_ebitda=debt_to_ebitda,
        avg_volume=avg_volume,
        current_price=current_price,
        previous_close=previous_close,
        pre_market_price=pre_market_price,
    )


@pytest.fixture
def qualifying_stock() -> StockProfile:
    """A stock that passes all universe filters."""
    return make_stock(symbol="GOOD")


@pytest.fixture
def mock_provider(qualifying_stock: StockProfile) -> MockMarketDataProvider:
    """Provider with a mix of qualifying and non-qualifying stocks."""
    stocks = {
        "GOOD": qualifying_stock,
        "SMALL": make_stock(symbol="SMALL", market_cap=5_000_000_000),  # Below $10B
        "LOSER": make_stock(symbol="LOSER", net_income=-100_000_000),  # Negative income
        "LOWROE": make_stock(symbol="LOWROE", roe=0.05),  # ROE below 10%
        "DEBT": make_stock(symbol="DEBT", debt_to_ebitda=6.0),  # Debt/EBITDA above 4
        "ILLIQUID": make_stock(symbol="ILLIQUID", avg_volume=500_000),  # Volume below 2M
    }
    return MockMarketDataProvider(stocks)
