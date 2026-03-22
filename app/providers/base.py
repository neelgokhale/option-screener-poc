"""Abstract base classes for market data providers.

The provider layer defines the contract between the screening engine and
whatever data source is in use. Each ABC declares the methods the engine
needs. Concrete implementations (e.g., YahooFinanceProvider) fulfill these
contracts. This lets us swap providers without touching business logic —
just register a new subclass.
"""

from abc import ABC, abstractmethod

import pandas as pd

from app.models.option import Headline, OptionsChain
from app.models.stock import StockProfile


class MarketDataProvider(ABC):
    """Provides stock fundamentals and price history."""

    @abstractmethod
    def get_stock_info(self, symbol: str) -> StockProfile | None:
        """Fetch fundamental data for a single symbol.

        Returns None if the symbol is invalid or data is unavailable.
        """
        ...

    @abstractmethod
    def get_price_history(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch OHLCV price history.

        Args:
            symbol: Ticker symbol.
            period: Lookback period (e.g., "3mo", "1y").
            interval: Bar interval (e.g., "1d", "1h").

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Index is a DatetimeIndex.
        """
        ...

    @abstractmethod
    def get_sp500_symbols(self) -> list[str]:
        """Return a list of current S&P 500 constituent symbols."""
        ...


class OptionsDataProvider(ABC):
    """Provides options chain data."""

    @abstractmethod
    def get_expiry_dates(self, symbol: str) -> list[str]:
        """Return available expiry dates for the symbol (ISO format strings)."""
        ...

    @abstractmethod
    def get_options_chain(self, symbol: str, expiry: str) -> OptionsChain:
        """Fetch the full options chain for a symbol and expiry date.

        Args:
            symbol: Ticker symbol.
            expiry: Expiry date as ISO string (YYYY-MM-DD).
        """
        ...


class NewsProvider(ABC):
    """Provides recent news headlines for risk filtering."""

    @abstractmethod
    def get_recent_headlines(
        self, symbol: str, hours: int = 24
    ) -> list[Headline]:
        """Fetch recent headlines for a symbol.

        Args:
            symbol: Ticker symbol.
            hours: How far back to look (default 24h).
        """
        ...
