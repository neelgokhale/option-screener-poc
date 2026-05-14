"""Thin adapters translating provider ABCs to AVClient calls."""

import json
import logging
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from app.models.option import Headline, OptionContract, OptionsChain
from app.models.stock import StockProfile
from app.providers.av_client import AVClient
from app.providers.base import MarketDataProvider, NewsProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

_SP500_FILE = __import__("pathlib").Path(__file__).parent.parent / "data" / "sp500.json"


def _safe_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "None" or value == "-":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: str | None, default: int = 0) -> int:
    if value is None or value == "None" or value == "-":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class AVMarketDataAdapter(MarketDataProvider):
    def __init__(self, client: AVClient) -> None:
        self._client = client

    def get_stock_info(
        self, symbol: str, *, as_of: date | None = None
    ) -> StockProfile | None:
        try:
            overview = self._client.get_overview(symbol, as_of=as_of)
            balance = self._client.get_balance_sheet(symbol, as_of=as_of)
        except Exception:
            logger.warning("Failed to fetch stock info for %s", symbol, exc_info=True)
            return None

        if not overview.get("Symbol"):
            return None

        ebitda = _safe_float(overview.get("EBITDA"))
        quarterly = balance.get("quarterlyReports", [])
        total_debt = 0.0
        if quarterly:
            total_debt = _safe_float(quarterly[0].get("shortLongTermDebtTotal"))

        debt_to_ebitda = (total_debt / ebitda) if ebitda > 0 else float("inf")

        current_price = _safe_float(
            overview.get("50DayMovingAverage"),
            _safe_float(overview.get("AnalystTargetPrice")),
        )

        return StockProfile(
            symbol=overview["Symbol"],
            name=overview.get("Name", symbol),
            sector=overview.get("Sector", "Unknown"),
            market_cap=_safe_float(overview.get("MarketCapitalization")),
            net_income=0.0,
            roe=_safe_float(overview.get("ReturnOnEquityTTM")),
            debt_to_ebitda=debt_to_ebitda,
            avg_volume=0.0,
            current_price=current_price,
            previous_close=current_price,
            beta=_safe_float(overview.get("Beta")) or None,
        )

    def get_price_history(
        self,
        symbol: str,
        period: str = "3mo",
        interval: str = "1d",
        *,
        as_of: date | None = None,
    ) -> pd.DataFrame:
        try:
            data = self._client.get_price_history(symbol, as_of=as_of)
        except Exception:
            logger.warning("Failed to fetch price history for %s", symbol, exc_info=True)
            return pd.DataFrame()

        ts_key = next(
            (k for k in data if "Time Series" in k),
            None,
        )
        if ts_key is None:
            return pd.DataFrame()

        series = data[ts_key]
        rows = []
        for date_str, values in series.items():
            rows.append({
                "Date": pd.Timestamp(date_str),
                "Open": _safe_float(values.get("1. open")),
                "High": _safe_float(values.get("2. high")),
                "Low": _safe_float(values.get("3. low")),
                "Close": _safe_float(values.get("4. close")),
                "Volume": _safe_int(values.get("6. volume",
                                               values.get("5. volume"))),
            })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).set_index("Date").sort_index()

        if as_of is not None:
            df = df[df.index <= pd.Timestamp(as_of)]

        return df

    def get_sp500_symbols(self) -> list[str]:
        try:
            with open(_SP500_FILE) as f:
                return json.load(f)
        except Exception:
            logger.warning("Failed to load S&P 500 list", exc_info=True)
            return []


class AVOptionsAdapter(OptionsDataProvider):
    def __init__(self, client: AVClient) -> None:
        self._client = client

    def get_expiry_dates(
        self, symbol: str, *, as_of: date | None = None
    ) -> list[str]:
        data = self._client.get_options_chain(symbol, as_of=as_of)
        expiries = sorted({c["expiration"] for c in data.get("data", [])})
        return expiries

    def get_options_chain(
        self, symbol: str, expiry: str, *, as_of: date | None = None
    ) -> OptionsChain:
        data = self._client.get_options_chain(symbol, as_of=as_of)
        expiry_date = date.fromisoformat(expiry)

        puts = []
        calls = []
        for c in data.get("data", []):
            if c["expiration"] != expiry:
                continue
            contract = OptionContract(
                symbol=symbol,
                expiry=expiry_date,
                strike=_safe_float(c.get("strike")),
                option_type=c.get("type", "put"),
                bid=_safe_float(c.get("bid")),
                ask=_safe_float(c.get("ask")),
                last_price=_safe_float(c.get("last")),
                delta=_safe_float(c.get("delta")) or None,
                theta=_safe_float(c.get("theta")) or None,
                gamma=_safe_float(c.get("gamma")) or None,
                implied_volatility=_safe_float(c.get("implied_volatility")),
                open_interest=_safe_int(c.get("open_interest")),
                volume=_safe_int(c.get("volume")),
            )
            if c.get("type") == "put":
                puts.append(contract)
            else:
                calls.append(contract)

        return OptionsChain(symbol=symbol, expiry=expiry_date, puts=puts, calls=calls)


class AVNewsAdapter(NewsProvider):
    def __init__(self, client: AVClient) -> None:
        self._client = client

    def get_recent_headlines(
        self, symbol: str, hours: int = 24, *, as_of: date | None = None
    ) -> list[Headline]:
        ref_time = datetime.now(timezone.utc)
        if as_of is not None:
            ref_time = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)

        time_from = (ref_time - timedelta(hours=hours)).strftime("%Y%m%dT%H%M")
        time_to = ref_time.strftime("%Y%m%dT%H%M") if as_of is not None else None

        try:
            data = self._client.get_news_sentiment(
                symbol, time_from=time_from, time_to=time_to
            )
        except Exception:
            logger.warning("News fetch failed for %s", symbol, exc_info=True)
            return []

        headlines = []
        for article in data.get("feed", []):
            sentiment = None
            relevance = None
            for ts in article.get("ticker_sentiment", []):
                if ts.get("ticker") == symbol:
                    sentiment = _safe_float(ts.get("ticker_sentiment_score")) or None
                    relevance = _safe_float(ts.get("relevance_score")) or None
                    break
            headlines.append(Headline(
                title=article.get("title", ""),
                source=article.get("source", ""),
                published_at=article.get("time_published", ""),
                url=article.get("url"),
                ticker_sentiment_score=sentiment,
                relevance_score=relevance,
            ))
        return headlines
