"""Safety score calculation (PRD §3.7).

Each trade receives a Safety Score (0-1) based on six weighted factors.
The score adjusts the final ranking so safer trades rise to the top.

Components and weights:
    Distance from support    25%  — how far the strike is below support
    Pre-market stability     15%  — how calm the stock is pre-market
    Sector correlation       10%  — lower SPY correlation = more diversified
    IV rank stability        15%  — lower IV rank = less volatile environment
    Institutional flow       20%  — put/call OI ratio as flow proxy
    Market risk              15%  — VIX-based broad market score

Final formula:
    Adjusted Score = Put Opportunity Score × (1 + Safety Score)
"""

import logging

import numpy as np
import pandas as pd

from app.models.market import MarketRiskStatus
from app.models.option import ScreenedTrade
from app.models.safety import SafetyComponents, SafetyResult
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

# Component weights (must sum to 1.0)
W_DISTANCE = 0.25
W_PREMARKET = 0.15
W_CORRELATION = 0.10
W_IV_RANK = 0.15
W_FLOW = 0.20
W_MARKET = 0.15


def calculate_safety_score(
    trade: ScreenedTrade,
    profile: StockProfile,
    market_risk: MarketRiskStatus,
    market_provider: MarketDataProvider,
    options_provider: OptionsDataProvider,
) -> SafetyResult:
    """Compute the composite safety score for a screened trade.

    Each component is normalized to 0-1, where 1 = safest.
    The composite is the weighted sum.
    """
    dist = _distance_from_support(trade)
    premarket = _premarket_stability(profile)
    corr = _sector_correlation(profile.symbol, market_provider)
    iv_rank = _iv_rank_stability(trade)
    flow = _institutional_flow(trade, options_provider)
    market = _market_risk_score(market_risk)

    components = SafetyComponents(
        distance_from_support=dist,
        pre_market_stability=premarket,
        sector_correlation=corr,
        iv_rank_stability=iv_rank,
        institutional_flow=flow,
        market_risk=market,
    )

    score = (
        W_DISTANCE * dist
        + W_PREMARKET * premarket
        + W_CORRELATION * corr
        + W_IV_RANK * iv_rank
        + W_FLOW * flow
        + W_MARKET * market
    )

    return SafetyResult(score=round(score, 4), components=components)


def calculate_adjusted_score(ev: float, safety_score: float) -> float:
    """Apply the safety multiplier to the raw EV.

    Adjusted Score = EV × (1 + Safety Score)

    A safety score of 0.5 boosts EV by 50%. This rewards trades
    that are both high-EV and safe.
    """
    return ev * (1.0 + safety_score)


def _distance_from_support(trade: ScreenedTrade) -> float:
    """How far below the current price the strike sits, relative to support.

    Larger gap = safer. Normalized: (price - strike) / price, clamped to [0, 1].
    """
    if trade.current_price <= 0:
        return 0.0
    gap = (trade.current_price - trade.strike) / trade.current_price
    return min(max(gap, 0.0), 1.0)


def _premarket_stability(profile: StockProfile) -> float:
    """How stable the stock is in pre-market.

    Score = 1 - (|premarket_change| / 3%), clamped to [0, 1].
    If no pre-market data, assume stable (score = 1.0).
    """
    if profile.pre_market_price is None or profile.previous_close <= 0:
        return 1.0  # No data = assume stable

    change = abs(profile.pre_market_price - profile.previous_close) / profile.previous_close
    score = 1.0 - (change / 0.03)
    return min(max(score, 0.0), 1.0)


def _sector_correlation(symbol: str, provider: MarketDataProvider) -> float:
    """Inverse correlation with SPY over 30 days.

    Lower correlation = more diversification benefit = higher score.
    Score = 1 - |correlation|, so uncorrelated stocks score highest.
    """
    try:
        stock_hist = provider.get_price_history(symbol, period="2mo", interval="1d")
        spy_hist = provider.get_price_history("SPY", period="2mo", interval="1d")

        if stock_hist.empty or spy_hist.empty or len(stock_hist) < 20:
            return 0.5  # Default if insufficient data

        stock_returns = stock_hist["Close"].pct_change().dropna().iloc[-30:]
        spy_returns = spy_hist["Close"].pct_change().dropna().iloc[-30:]

        # Align lengths
        min_len = min(len(stock_returns), len(spy_returns))
        if min_len < 10:
            return 0.5

        corr = np.corrcoef(
            stock_returns.iloc[-min_len:].values,
            spy_returns.iloc[-min_len:].values,
        )[0, 1]

        if np.isnan(corr):
            return 0.5

        return round(1.0 - abs(corr), 4)
    except Exception:
        logger.warning("Correlation calc failed for %s", symbol, exc_info=True)
        return 0.5


def _iv_rank_stability(trade: ScreenedTrade) -> float:
    """Score based on implied volatility level.

    Lower IV = more stable environment = higher score.
    We map IV to a 0-1 score: IV of 0.15 → 1.0, IV of 0.60+ → 0.0.
    This is a simplified IV rank (true IV rank needs 52-week IV history).
    """
    iv = trade.implied_volatility
    # Linear scale: 0.15 → 1.0, 0.60 → 0.0
    score = 1.0 - (iv - 0.15) / (0.60 - 0.15)
    return min(max(score, 0.0), 1.0)


def _institutional_flow(
    trade: ScreenedTrade,
    options_provider: OptionsDataProvider,
) -> float:
    """Put/call open interest ratio as a proxy for institutional flow.

    High put OI relative to call OI suggests institutional hedging,
    which implies support for the stock. Higher ratio = higher score.

    POC simplification: uses the same expiry chain that the trade is from.
    """
    try:
        chain = options_provider.get_options_chain(
            trade.symbol, trade.expiry.isoformat()
        )
        total_put_oi = sum(p.open_interest for p in chain.puts)
        total_call_oi = sum(c.open_interest for c in chain.calls)

        if total_call_oi == 0:
            return 0.5  # No data

        # Put/call ratio. A ratio of 1.0 = neutral, >1 = bearish hedging = supportive
        pc_ratio = total_put_oi / total_call_oi

        # Normalize: ratio of 0.5 → 0.0, ratio of 1.5+ → 1.0
        score = (pc_ratio - 0.5) / (1.5 - 0.5)
        return min(max(score, 0.0), 1.0)
    except Exception:
        logger.warning("Flow calc failed for %s", trade.symbol, exc_info=True)
        return 0.5


def _market_risk_score(market_risk: MarketRiskStatus) -> float:
    """Score based on VIX level.

    Low VIX = calm market = high score.
    VIX 12 → 1.0, VIX 30+ → 0.0.
    """
    vix = market_risk.vix_level
    score = 1.0 - (vix - 12.0) / (30.0 - 12.0)
    return min(max(score, 0.0), 1.0)
