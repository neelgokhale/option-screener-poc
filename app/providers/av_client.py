"""AlphaVantage HTTP client with rate limiting, retry, and cache integration."""

import logging
import sqlite3
import time
from collections import deque
from datetime import date

import httpx

from app.providers.av_cache import AVCache

logger = logging.getLogger(__name__)

AV_BASE_URL = "https://www.alphavantage.co/query"
RATE_LIMIT = 75
RATE_WINDOW = 60  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 1.0


class AVClient:
    def __init__(
        self,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        db_conn: sqlite3.Connection | None = None,
    ) -> None:
        self._api_key = api_key
        self._call_times: deque[float] = deque()
        client_kwargs: dict = {"timeout": 30.0}
        if transport is not None:
            client_kwargs["transport"] = transport
        self._http = httpx.Client(**client_kwargs)
        self._cache = AVCache(db_conn) if db_conn is not None else None

    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        while self._call_times and (now - self._call_times[0]) > RATE_WINDOW:
            self._call_times.popleft()

        if len(self._call_times) >= RATE_LIMIT:
            sleep_time = RATE_WINDOW - (now - self._call_times[0]) + 0.1
            if sleep_time > 0:
                logger.info("Rate limit reached, sleeping %.1fs", sleep_time)
                time.sleep(sleep_time)

        self._call_times.append(time.monotonic())

    def _request(self, function: str, params: dict) -> dict:
        self._wait_for_rate_limit()

        params = {**params, "function": function, "apikey": self._api_key}

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._http.get(AV_BASE_URL, params=params)
                if resp.status_code in (429,) or resp.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF * (2 ** attempt)
                        logger.warning("%d from AV, retrying in %.1fs", resp.status_code, wait)
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.json()
            except httpx.TransportError:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * (2 ** attempt)
                    logger.warning("Network error, retrying in %.1fs", wait)
                    time.sleep(wait)
                    continue
                raise

        raise RuntimeError("Exhausted retries")

    def _cached_request(
        self,
        cache_key: str,
        ttl_seconds: int,
        function: str,
        params: dict,
        *,
        bypass_cache: bool = False,
    ) -> dict:
        if self._cache is None:
            return self._request(function, params)
        return self._cache.get_or_fetch(
            cache_key,
            ttl_seconds,
            lambda: self._request(function, params),
            bypass_cache=bypass_cache,
        )

    # --- TTL constants (seconds) ---
    TTL_7_DAYS = 7 * 24 * 3600
    TTL_24H = 24 * 3600
    TTL_1H = 3600
    TTL_FOREVER = 100 * 365 * 24 * 3600

    def get_overview(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        return self._cached_request(
            f"overview:{symbol}",
            self.TTL_7_DAYS,
            "OVERVIEW",
            {"symbol": symbol},
            bypass_cache=bypass_cache,
        )

    def get_balance_sheet(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        return self._cached_request(
            f"balance_sheet:{symbol}",
            self.TTL_7_DAYS,
            "BALANCE_SHEET",
            {"symbol": symbol},
            bypass_cache=bypass_cache,
        )

    def get_price_history(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        is_current = as_of is None or as_of >= date.today()
        ttl = self.TTL_24H if is_current else self.TTL_FOREVER
        cache_key = f"daily:{symbol}:{as_of or 'latest'}"
        return self._cached_request(
            cache_key,
            ttl,
            "TIME_SERIES_DAILY_ADJUSTED",
            {"symbol": symbol, "outputsize": "full"},
            bypass_cache=bypass_cache,
        )

    def get_options_chain(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        target_date = as_of or date.today()
        is_today = target_date >= date.today()
        ttl = self.TTL_24H if is_today else self.TTL_FOREVER
        params: dict = {"symbol": symbol}
        if as_of is not None:
            params["date"] = as_of.isoformat()
        return self._cached_request(
            f"options:{symbol}:{target_date.isoformat()}",
            ttl,
            "HISTORICAL_OPTIONS",
            params,
            bypass_cache=bypass_cache,
        )

    def get_vix(
        self,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        return self._cached_request(
            "vix:daily",
            self.TTL_24H,
            "INDEX_DATA",
            {"symbol": "VIX", "interval": "daily"},
            bypass_cache=bypass_cache,
        )

    def get_earnings(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        return self._cached_request(
            f"earnings:{symbol}",
            self.TTL_FOREVER,
            "EARNINGS",
            {"symbol": symbol},
            bypass_cache=bypass_cache,
        )

    def get_earnings_calendar(
        self,
        *,
        symbol: str | None = None,
        horizon: str = "3month",
        bypass_cache: bool = False,
    ) -> str:
        self._wait_for_rate_limit()
        params: dict = {
            "function": "EARNINGS_CALENDAR",
            "horizon": horizon,
            "apikey": self._api_key,
        }
        if symbol is not None:
            params["symbol"] = symbol
        resp = self._http.get(AV_BASE_URL, params=params)
        resp.raise_for_status()
        return resp.text

    def get_news_sentiment(
        self,
        symbol: str,
        *,
        as_of: date | None = None,
        time_from: str | None = None,
        time_to: str | None = None,
        bypass_cache: bool = False,
    ) -> dict:
        params: dict = {"tickers": symbol, "sort": "LATEST", "limit": "1000"}
        if time_from:
            params["time_from"] = time_from
        if time_to:
            params["time_to"] = time_to

        is_historical = time_to is not None
        ttl = self.TTL_FOREVER if is_historical else self.TTL_1H
        cache_key = f"news:{symbol}:{time_from or 'none'}:{time_to or 'latest'}"

        return self._cached_request(
            cache_key, ttl, "NEWS_SENTIMENT", params, bypass_cache=bypass_cache,
        )
