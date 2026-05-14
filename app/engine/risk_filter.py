"""Risk filtering layer.

Two filters that exclude stocks with elevated near-term risk:

1. Sentiment filter — exclude when AV NEWS_SENTIMENT has
   ticker_sentiment_score < -0.35 AND relevance_score > 0.5
2. Earnings filter — exclude stocks with earnings within 21 days
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, NewsProvider

logger = logging.getLogger(__name__)

SENTIMENT_THRESHOLD = -0.35
RELEVANCE_THRESHOLD = 0.5
EARNINGS_EXCLUSION_DAYS = 21


@dataclass
class RiskFilterResult:
    """Tracks which stocks were excluded by risk filters."""

    passed: list[str] = field(default_factory=list)
    excluded_sentiment: list[str] = field(default_factory=list)
    excluded_earnings: list[str] = field(default_factory=list)


def apply_risk_filters(
    symbols: list[str],
    profiles: dict[str, StockProfile],
    market_provider: MarketDataProvider,
    news_provider: NewsProvider | None = None,
    as_of: date | None = None,
) -> RiskFilterResult:
    result = RiskFilterResult()

    after_earnings: list[str] = []

    for symbol in symbols:
        profile = profiles.get(symbol)
        if profile is None:
            continue

        if _has_upcoming_earnings(symbol, market_provider, as_of=as_of):
            result.excluded_earnings.append(symbol)
            continue

        after_earnings.append(symbol)

    for symbol in after_earnings:
        if news_provider is not None:
            if _has_negative_sentiment(symbol, news_provider, as_of=as_of):
                result.excluded_sentiment.append(symbol)
                continue

        result.passed.append(symbol)

    logger.info(
        "Risk filter: %d passed, %d excluded (sentiment=%d, earnings=%d)",
        len(result.passed),
        len(result.excluded_sentiment) + len(result.excluded_earnings),
        len(result.excluded_sentiment),
        len(result.excluded_earnings),
    )

    return result


def _has_negative_sentiment(
    symbol: str, news_provider: NewsProvider, *, as_of: date | None = None
) -> bool:
    try:
        headlines = news_provider.get_recent_headlines(symbol, hours=24, as_of=as_of)
        for headline in headlines:
            score = headline.ticker_sentiment_score
            relevance = headline.relevance_score
            if (
                score is not None
                and relevance is not None
                and score < SENTIMENT_THRESHOLD
                and relevance > RELEVANCE_THRESHOLD
            ):
                logger.debug(
                    "Negative sentiment for %s: score=%.2f, relevance=%.2f",
                    symbol, score, relevance,
                )
                return True
        return False
    except Exception:
        logger.warning("Sentiment check failed for %s, allowing through", symbol, exc_info=True)
        return False


def _has_upcoming_earnings(
    symbol: str, provider: MarketDataProvider, *, as_of: date | None = None
) -> bool:
    """Check if earnings are within 21 days.

    yfinance's ticker.calendar returns a dict with:
        'Earnings Date': [datetime.date, ...] — list of upcoming dates

    Returns False if data is unavailable (we'd rather include the
    stock than wrongly exclude it).
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        calendar = ticker.calendar

        if not calendar or not isinstance(calendar, dict):
            return False

        earnings_dates = calendar.get("Earnings Date")
        if not earnings_dates:
            return False

        # earnings_dates is a list of date objects
        if not isinstance(earnings_dates, list):
            earnings_dates = [earnings_dates]

        today = as_of or date.today()
        for ed in earnings_dates:
            # Convert to date if it's a datetime
            if hasattr(ed, "date"):
                ed = ed.date()
            elif isinstance(ed, str):
                ed = date.fromisoformat(ed)

            days_until = (ed - today).days
            if 0 <= days_until <= EARNINGS_EXCLUSION_DAYS:
                logger.debug(
                    "Earnings for %s in %d days (%s)", symbol, days_until, ed
                )
                return True

        return False
    except Exception:
        logger.warning("Earnings check failed for %s, allowing through", symbol, exc_info=True)
        return False
