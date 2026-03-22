"""Stock universe filter.

Applies fundamental filters from the PRD to narrow the S&P 500 down to
stocks suitable for short-put screening. Each filter is a simple threshold
check against the StockProfile fields.

Filter criteria (from PRD §3.1):
- Market cap > $10B
- Positive net income
- ROE > 10%
- Debt / EBITDA < 4
- Average daily volume > 2M shares
- Options open interest > 1000 contracts (checked later during options screening)

The open interest filter is deferred to the options screener because it
applies per-contract, not per-stock.
"""

import logging
from dataclasses import dataclass, field

from app.models.stock import StockProfile, UniverseFilterResult
from app.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

MIN_MARKET_CAP = 10_000_000_000  # $10B
MIN_ROE = 0.10  # 10%
MAX_DEBT_TO_EBITDA = 4.0
MIN_AVG_VOLUME = 2_000_000  # 2M shares/day


@dataclass
class _FilterTracker:
    """Tracks which symbols were excluded and why."""

    excluded: dict[str, list[str]] = field(default_factory=dict)

    def exclude(self, symbol: str, reason: str) -> None:
        self.excluded.setdefault(reason, []).append(symbol)


def filter_universe(
    provider: MarketDataProvider,
    symbols: list[str] | None = None,
) -> UniverseFilterResult:
    """Run fundamental filters on S&P 500 stocks.

    Args:
        provider: Market data provider to fetch stock info from.
        symbols: Optional override list of symbols. If None, uses S&P 500.

    Returns:
        UniverseFilterResult with qualified symbols and exclusion details.
    """
    if symbols is None:
        symbols = provider.get_sp500_symbols()

    tracker = _FilterTracker()
    qualified: list[str] = []

    for symbol in symbols:
        profile = provider.get_stock_info(symbol)

        if profile is None:
            tracker.exclude(symbol, "data_unavailable")
            continue

        if not _passes_filters(profile, tracker):
            continue

        qualified.append(symbol)

    logger.info(
        "Universe filter: %d/%d symbols qualified",
        len(qualified),
        len(symbols),
    )

    return UniverseFilterResult(
        qualified=qualified,
        total_scanned=len(symbols),
        filtered_out=tracker.excluded,
    )


def _passes_filters(profile: StockProfile, tracker: _FilterTracker) -> bool:
    """Apply each fundamental filter in sequence.

    Returns True if the stock passes all filters. Records exclusion
    reason in the tracker for the first failed filter.
    """
    symbol = profile.symbol

    if profile.market_cap < MIN_MARKET_CAP:
        tracker.exclude(symbol, "market_cap_below_10B")
        return False

    if profile.net_income <= 0:
        tracker.exclude(symbol, "negative_net_income")
        return False

    if profile.roe < MIN_ROE:
        tracker.exclude(symbol, "roe_below_10pct")
        return False

    if profile.debt_to_ebitda > MAX_DEBT_TO_EBITDA:
        tracker.exclude(symbol, "debt_to_ebitda_above_4")
        return False

    if profile.avg_volume < MIN_AVG_VOLUME:
        tracker.exclude(symbol, "avg_volume_below_2M")
        return False

    return True
