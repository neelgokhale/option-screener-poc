"""Finnhub news provider for risk filtering.

Uses the Finnhub API (free tier: 60 calls/minute) to fetch
company-specific news headlines. We scan these for negative
keywords to identify stocks with elevated near-term risk.

Rate limiting: the provider tracks call timestamps and sleeps
when approaching the 60 calls/min limit. This is handled
transparently — callers don't need to worry about pacing.
"""

import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models.option import Headline
from app.providers.base import NewsProvider

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
RATE_LIMIT_CALLS = 55  # Stay under the 60/min limit with margin
RATE_LIMIT_WINDOW = 60  # seconds


class FinnhubNewsProvider(NewsProvider):
    """Fetches company news from the Finnhub API with rate limiting."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.finnhub_api_key
        self._call_times: deque[float] = deque()

    def _wait_for_rate_limit(self) -> None:
        """Block until we're under the rate limit."""
        now = time.monotonic()

        # Remove timestamps older than the window
        while self._call_times and (now - self._call_times[0]) > RATE_LIMIT_WINDOW:
            self._call_times.popleft()

        # If at the limit, sleep until the oldest call falls out of the window
        if len(self._call_times) >= RATE_LIMIT_CALLS:
            sleep_time = RATE_LIMIT_WINDOW - (now - self._call_times[0]) + 0.1
            if sleep_time > 0:
                logger.info("Rate limit reached, sleeping %.1fs", sleep_time)
                time.sleep(sleep_time)

        self._call_times.append(time.monotonic())

    def get_recent_headlines(
        self, symbol: str, hours: int = 24
    ) -> list[Headline]:
        if not self._api_key:
            logger.debug("No Finnhub API key configured, skipping news check")
            return []

        self._wait_for_rate_limit()

        now = datetime.now(timezone.utc)
        from_date = (now - timedelta(hours=hours)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        try:
            resp = httpx.get(
                f"{FINNHUB_BASE_URL}/company-news",
                params={
                    "symbol": symbol,
                    "from": from_date,
                    "to": to_date,
                    "token": self._api_key,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                Headline(
                    title=item.get("headline", ""),
                    source=item.get("source", ""),
                    published_at=datetime.fromtimestamp(
                        item.get("datetime", 0), tz=timezone.utc
                    ).isoformat(),
                    url=item.get("url"),
                )
                for item in data
                if item.get("headline")
            ]
        except Exception:
            logger.warning(
                "Finnhub news fetch failed for %s", symbol, exc_info=True
            )
            return []
