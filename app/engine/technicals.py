"""Technical support/resistance level calculation.

Uses a local-minima approach on daily price data to identify support levels.
The algorithm:
1. Fetch 60 days of daily OHLCV data
2. Find local minima: a day's low is a local min if it's the lowest
   in a window of N days on each side (default N=5)
3. Cluster nearby support levels within a tolerance (default 1%)
4. Return the nearest support level below the current price

This is a pragmatic heuristic for a POC. More sophisticated methods
(Fibonacci retracements, volume profile, order flow) can be added later.
"""

import logging

import numpy as np
import pandas as pd

from app.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

LOOKBACK_PERIOD = "3mo"
WINDOW_SIZE = 5  # Days on each side for local min detection
CLUSTER_TOLERANCE = 0.01  # 1% — levels within this range are merged


def find_support_level(
    provider: MarketDataProvider,
    symbol: str,
    current_price: float,
) -> float | None:
    """Find the nearest support level below the current price.

    Args:
        provider: Market data provider for price history.
        symbol: Ticker symbol.
        current_price: Current stock price.

    Returns:
        The nearest support level below current_price, or None if
        no support level is found (falls back to caller's default).
    """
    hist = provider.get_price_history(symbol, period=LOOKBACK_PERIOD)

    if hist.empty or len(hist) < WINDOW_SIZE * 2 + 1:
        logger.warning("Insufficient price history for %s", symbol)
        return None

    minima = _find_local_minima(hist)

    if not minima:
        return None

    clustered = _cluster_levels(minima)

    # Find the nearest support below current price
    supports_below = [s for s in clustered if s < current_price]

    if not supports_below:
        return None

    return max(supports_below)


def _find_local_minima(hist: pd.DataFrame) -> list[float]:
    """Identify local minima in the Low price series.

    A point is a local minimum if its Low is the lowest value within
    WINDOW_SIZE days on each side. This catches swing lows that act
    as natural support levels.
    """
    lows = hist["Low"].values
    minima: list[float] = []

    for i in range(WINDOW_SIZE, len(lows) - WINDOW_SIZE):
        window = lows[i - WINDOW_SIZE : i + WINDOW_SIZE + 1]
        if lows[i] == np.min(window):
            minima.append(float(lows[i]))

    return minima


def _cluster_levels(levels: list[float]) -> list[float]:
    """Merge support levels that are within CLUSTER_TOLERANCE of each other.

    When multiple swing lows land near the same price, they reinforce
    each other as a support zone. We merge them into a single level
    (the mean of the cluster) to avoid redundancy.
    """
    if not levels:
        return []

    sorted_levels = sorted(levels)
    clusters: list[list[float]] = [[sorted_levels[0]]]

    for level in sorted_levels[1:]:
        cluster_mean = sum(clusters[-1]) / len(clusters[-1])
        if abs(level - cluster_mean) / cluster_mean <= CLUSTER_TOLERANCE:
            clusters[-1].append(level)
        else:
            clusters.append([level])

    return [sum(c) / len(c) for c in clusters]
