"""Market risk monitoring via VIX and SPY trend.

Checks two broad market indicators (PRD §3.3):
1. VIX (^VIX) — fear gauge. Above 25 signals elevated volatility.
2. SPY trend — if SPY is below its 20-day SMA, the market is in
   a short-term downtrend.

When either condition is true, the pipeline reduces the trade list
by 50% (take top N/2 instead of top N). This prevents overexposure
during market stress.
"""

import logging

from app.models.market import MarketRiskStatus
from app.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

VIX_SYMBOL = "^VIX"
SPY_SYMBOL = "SPY"
VIX_THRESHOLD = 25.0
SMA_PERIOD = 20


def assess_market_risk(provider: MarketDataProvider) -> MarketRiskStatus:
    """Evaluate current market risk from VIX and SPY.

    Returns a MarketRiskStatus indicating whether risk is elevated
    and why. Used by the pipeline to decide how many trades to output.
    """
    vix_level = _get_vix(provider)
    spy_price, spy_sma = _get_spy_trend(provider)
    spy_above_sma = spy_price >= spy_sma

    reasons: list[str] = []
    if vix_level > VIX_THRESHOLD:
        reasons.append(f"VIX at {vix_level:.1f} (above {VIX_THRESHOLD})")
    if not spy_above_sma:
        reasons.append(f"SPY ({spy_price:.2f}) below 20-day SMA ({spy_sma:.2f})")

    risk_elevated = len(reasons) > 0

    if risk_elevated:
        logger.info("Market risk ELEVATED: %s", "; ".join(reasons))

    return MarketRiskStatus(
        vix_level=vix_level,
        vix_threshold=VIX_THRESHOLD,
        spy_price=spy_price,
        spy_sma_20=spy_sma,
        spy_above_sma=spy_above_sma,
        risk_elevated=risk_elevated,
        risk_reason="; ".join(reasons) if reasons else None,
    )


def _get_vix(provider: MarketDataProvider) -> float:
    """Fetch the current VIX level."""
    try:
        hist = provider.get_price_history(VIX_SYMBOL, period="5d", interval="1d")
        if hist.empty:
            return 0.0
        return float(hist["Close"].iloc[-1])
    except Exception:
        logger.warning("Failed to fetch VIX, defaulting to 0", exc_info=True)
        return 0.0


def _get_spy_trend(provider: MarketDataProvider) -> tuple[float, float]:
    """Fetch SPY current price and 20-day SMA.

    Returns (current_price, sma_20).
    """
    try:
        hist = provider.get_price_history(SPY_SYMBOL, period="2mo", interval="1d")
        if hist.empty or len(hist) < SMA_PERIOD:
            return 0.0, 0.0
        current = float(hist["Close"].iloc[-1])
        sma = float(hist["Close"].iloc[-SMA_PERIOD:].mean())
        return current, sma
    except Exception:
        logger.warning("Failed to fetch SPY trend, defaulting to 0", exc_info=True)
        return 0.0, 0.0
