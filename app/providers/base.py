"""Abstract base classes for market data providers."""

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from app.models.option import Headline, OptionsChain
from app.models.stock import StockProfile


class MarketDataProvider(ABC):

    @abstractmethod
    def get_stock_info(
        self, symbol: str, *, as_of: date | None = None
    ) -> StockProfile | None: ...

    @abstractmethod
    def get_price_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        *,
        as_of: date | None = None,
    ) -> pd.DataFrame: ...

    @abstractmethod
    def get_sp500_symbols(self) -> list[str]: ...


class OptionsDataProvider(ABC):

    @abstractmethod
    def get_expiry_dates(
        self, symbol: str, *, as_of: date | None = None
    ) -> list[str]: ...

    @abstractmethod
    def get_options_chain(
        self, symbol: str, expiry: str, *, as_of: date | None = None
    ) -> OptionsChain: ...


class NewsProvider(ABC):

    @abstractmethod
    def get_recent_headlines(
        self, symbol: str, hours: int = 24, *, as_of: date | None = None
    ) -> list[Headline]: ...
