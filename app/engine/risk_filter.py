"""Risk filtering layer (PRD §3.2).

Three filters that exclude stocks with elevated near-term risk:

1. News filter — scan 24h headlines for negative keywords
   (downgrades, litigation, regulatory actions, etc.)
2. Pre-market movement filter — exclude stocks moving > ±3% pre-market
3. Earnings filter — exclude stocks with earnings within 21 days

These filters run AFTER the universe filter but BEFORE options screening,
so we avoid wasting API calls on stocks we'd reject anyway.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, NewsProvider

logger = logging.getLogger(__name__)

# Keywords that signal elevated risk in headlines
NEGATIVE_KEYWORDS = [
    "downgrade",
    "downgrades",
    "downgraded",
    "lawsuit",
    "litigation",
    "sued",
    "sec investigation",
    "sec charges",
    "regulatory",
    "regulation",
    "fine",
    "penalty",
    "warning",
    "warns",
    "earnings warning",
    "profit warning",
    "layoff",
    "layoffs",
    "restructuring",
    "recall",
    "bankruptcy",
    "default",
    "fraud",
    "scandal",
    "probe",
    "investigation",
]

MAX_PREMARKET_CHANGE = 0.03  # 3%
EARNINGS_EXCLUSION_DAYS = 21


@dataclass
class RiskFilterResult:
    """Tracks which stocks were excluded by risk filters."""

    passed: list[str] = field(default_factory=list)
    excluded_news: list[str] = field(default_factory=list)
    excluded_premarket: list[str] = field(default_factory=list)
    excluded_earnings: list[str] = field(default_factory=list)


def apply_risk_filters(
    symbols: list[str],
    profiles: dict[str, StockProfile],
    market_provider: MarketDataProvider,
    news_provider: NewsProvider | None = None,
) -> RiskFilterResult:
    """Apply all risk filters to a list of symbols.

    Args:
        symbols: Symbols that passed the universe filter.
        profiles: Pre-fetched StockProfile data keyed by symbol.
        market_provider: For earnings date lookup.
        news_provider: For headline scanning. If None, news filter is skipped.

    Returns:
        RiskFilterResult with lists of passed and excluded symbols.
    """
    result = RiskFilterResult()

    # Run cheap filters first (no API calls) to reduce the pool
    # before hitting Finnhub's 60 calls/min rate limit.
    after_cheap_filters: list[str] = []

    for symbol in symbols:
        profile = profiles.get(symbol)
        if profile is None:
            continue

        # Filter 1: Pre-market movement (free — uses cached profile data)
        if _has_excessive_premarket_move(profile):
            result.excluded_premarket.append(symbol)
            continue

        # Filter 2: Earnings within 21 days (free — uses yfinance calendar)
        if _has_upcoming_earnings(symbol, market_provider):
            result.excluded_earnings.append(symbol)
            continue

        after_cheap_filters.append(symbol)

    # Filter 3: News headlines (expensive — 1 Finnhub API call per stock)
    # Run last, with rate limiting, on the reduced pool
    for symbol in after_cheap_filters:
        if news_provider is not None:
            if _has_negative_news(symbol, news_provider):
                result.excluded_news.append(symbol)
                continue

        result.passed.append(symbol)

    logger.info(
        "Risk filter: %d passed, %d excluded (news=%d, premarket=%d, earnings=%d)",
        len(result.passed),
        len(result.excluded_news) + len(result.excluded_premarket) + len(result.excluded_earnings),
        len(result.excluded_news),
        len(result.excluded_premarket),
        len(result.excluded_earnings),
    )

    return result


def _has_negative_news(symbol: str, news_provider: NewsProvider) -> bool:
    """Check if any recent headlines contain negative keywords."""
    try:
        headlines = news_provider.get_recent_headlines(symbol, hours=24)
        for headline in headlines:
            title_lower = headline.title.lower()
            if any(kw in title_lower for kw in NEGATIVE_KEYWORDS):
                logger.debug("Negative news for %s: %s", symbol, headline.title)
                return True
        return False
    except Exception:
        logger.warning("News check failed for %s, allowing through", symbol, exc_info=True)
        return False


def _has_excessive_premarket_move(profile: StockProfile) -> bool:
    """Check if pre-market price change exceeds ±3%.

    Returns False if pre-market data is unavailable (common after hours).
    """
    if profile.pre_market_price is None or profile.previous_close <= 0:
        return False

    change = abs(profile.pre_market_price - profile.previous_close) / profile.previous_close
    if change > MAX_PREMARKET_CHANGE:
        logger.debug(
            "Pre-market move for %s: %.1f%%",
            profile.symbol,
            change * 100,
        )
        return True
    return False


def _has_upcoming_earnings(symbol: str, provider: MarketDataProvider) -> bool:
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

        today = date.today()
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
