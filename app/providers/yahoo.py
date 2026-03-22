"""Yahoo Finance provider using the yfinance library.

yfinance scrapes data from Yahoo Finance. It's free and needs no API key,
making it ideal for a POC. The trade-off is that it can be rate-limited
and data may occasionally be stale for less liquid names.

Key implementation notes:
- yfinance is synchronous, so calls block. In the pipeline we wrap these
  in a ThreadPoolExecutor for parallelism (see engine/pipeline.py).
- ticker.info returns a dict with inconsistent keys across symbols.
  We defensively use .get() with fallbacks throughout.
- Options chain data includes greeks only when Yahoo provides them.
  Delta may be None for some contracts.
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

from app.models.option import OptionContract, OptionsChain
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

_SP500_FILE = Path(__file__).parent.parent / "data" / "sp500.json"


class YahooFinanceProvider(MarketDataProvider, OptionsDataProvider):
    """Concrete provider backed by yfinance.

    Implements both MarketDataProvider and OptionsDataProvider since
    yfinance exposes both stock fundamentals and options chains through
    the same Ticker object.
    """

    def get_stock_info(self, symbol: str) -> StockProfile | None:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or "symbol" not in info:
                return None

            # yfinance returns ROE as a decimal (e.g., 0.25 for 25%)
            roe = info.get("returnOnEquity")
            if roe is None:
                return None

            # Debt-to-EBITDA: compute from total debt and EBITDA
            total_debt = info.get("totalDebt", 0)
            ebitda = info.get("ebitda", 0)
            debt_to_ebitda = (total_debt / ebitda) if ebitda and ebitda > 0 else float("inf")

            return StockProfile(
                symbol=info.get("symbol", symbol),
                name=info.get("shortName", symbol),
                sector=info.get("sector", "Unknown"),
                market_cap=info.get("marketCap", 0),
                net_income=info.get("netIncomeToCommon", 0),
                roe=roe,
                debt_to_ebitda=debt_to_ebitda,
                avg_volume=info.get("averageVolume", 0),
                current_price=info.get("currentPrice", info.get("regularMarketPrice", 0)),
                previous_close=info.get("previousClose", 0),
                pre_market_price=info.get("preMarketPrice"),
            )
        except Exception:
            logger.warning("Failed to fetch stock info for %s", symbol, exc_info=True)
            return None

    def get_price_history(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        return hist

    def get_sp500_symbols(self) -> list[str]:
        """Load S&P 500 constituents from the static JSON file.

        The list is maintained in app/data/sp500.json and updated
        manually when constituents change (~20 times/year).
        """
        try:
            with open(_SP500_FILE) as f:
                return json.load(f)
        except Exception:
            logger.warning("Failed to load S&P 500 list from file", exc_info=True)
            return _FALLBACK_SYMBOLS

    def get_expiry_dates(self, symbol: str) -> list[str]:
        ticker = yf.Ticker(symbol)
        return list(ticker.options)

    def get_options_chain(self, symbol: str, expiry: str) -> OptionsChain:
        ticker = yf.Ticker(symbol)
        chain = ticker.option_chain(expiry)
        expiry_date = date.fromisoformat(expiry)

        puts = [
            self._row_to_contract(row, symbol, expiry_date, "put")
            for _, row in chain.puts.iterrows()
        ]
        calls = [
            self._row_to_contract(row, symbol, expiry_date, "call")
            for _, row in chain.calls.iterrows()
        ]

        return OptionsChain(
            symbol=symbol,
            expiry=expiry_date,
            puts=puts,
            calls=calls,
        )

    @staticmethod
    def _safe_int(value: object, default: int = 0) -> int:
        """Convert a value to int, handling NaN and None."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return int(value)

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        """Convert a value to float, handling NaN and None."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)

    @classmethod
    def _row_to_contract(
        cls, row: pd.Series, symbol: str, expiry: date, option_type: str
    ) -> OptionContract:
        """Convert a yfinance options DataFrame row to an OptionContract."""
        return OptionContract(
            symbol=symbol,
            expiry=expiry,
            strike=cls._safe_float(row.get("strike")),
            option_type=option_type,
            bid=cls._safe_float(row.get("bid")),
            ask=cls._safe_float(row.get("ask")),
            last_price=cls._safe_float(row.get("lastPrice")),
            delta=None,  # yfinance doesn't reliably provide greeks
            theta=None,
            gamma=None,
            implied_volatility=cls._safe_float(row.get("impliedVolatility")),
            open_interest=cls._safe_int(row.get("openInterest")),
            volume=cls._safe_int(row.get("volume")),
        )


# Minimal fallback in case Wikipedia scrape fails.
# These are large, liquid names likely to have good options data.
_FALLBACK_SYMBOLS = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AMD", "AMGN", "AMZN",
    "AVGO", "BAC", "BRK-B", "CAT", "COP", "COST", "CRM", "CSCO",
    "CVX", "DHR", "DIS", "GE", "GOOG", "GOOGL", "GS", "HD", "HON",
    "IBM", "INTC", "JNJ", "JPM", "KO", "LIN", "LLY", "LOW", "MA",
    "MCD", "MDT", "META", "MRK", "MSFT", "NEE", "NFLX", "NKE",
    "NVDA", "ORCL", "PEP", "PFE", "PG", "PM", "QCOM", "RTX",
    "SBUX", "SCHW", "SO", "SPY", "T", "TMO", "TMUS", "TSLA",
    "TXN", "UNH", "UNP", "UPS", "V", "VZ", "WFC", "WMT", "XOM",
]
