"""Safety score calculation.

Each trade receives a Safety Score (0-1) based on six weighted factors.
The score adjusts the final ranking so safer trades rise to the top.

Final formula:
    Adjusted Score = EV × (1 + Safety Score)
"""

import logging
from datetime import date

from app.models.market import MarketRiskStatus
from app.models.option import ScreenedTrade
from app.models.safety import SafetyComponents, SafetyResult
from app.models.stock import StockProfile
from app.providers.base import NewsProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

# Component weights (must sum to 1.0)
W_DISTANCE = 0.25
W_CORRELATION = 0.10
W_IV_RANK = 0.15
W_FLOW = 0.25
W_MARKET = 0.15
W_SENTIMENT = 0.10


def calculate_safety_score(
    trade: ScreenedTrade,
    profile: StockProfile,
    market_risk: MarketRiskStatus,
    options_provider: OptionsDataProvider,
    news_provider: NewsProvider | None = None,
    *,
    as_of: date | None = None,
) -> SafetyResult:
    dist = _distance_from_support(trade)
    corr = _beta_correlation(profile)
    iv_rank = _iv_rank_stability(trade)
    flow = _institutional_flow(trade, options_provider, as_of=as_of)
    market = _market_risk_score(market_risk)
    sent = (
        _sentiment_score(trade.symbol, news_provider, as_of=as_of)
        if news_provider is not None
        else 0.5
    )

    components = SafetyComponents(
        distance_from_support=dist,
        sector_correlation=corr,
        iv_rank_stability=iv_rank,
        institutional_flow=flow,
        market_risk=market,
        sentiment=sent,
    )

    score = (
        W_DISTANCE * dist
        + W_CORRELATION * corr
        + W_IV_RANK * iv_rank
        + W_FLOW * flow
        + W_MARKET * market
        + W_SENTIMENT * sent
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


def _beta_correlation(profile: StockProfile) -> float:
    if profile.beta is None:
        return 0.5
    return round(1.0 - min(abs(profile.beta), 1.0), 4)


def _sentiment_score(
    symbol: str, news_provider: NewsProvider, *, as_of: date | None = None
) -> float:
    try:
        headlines = news_provider.get_recent_headlines(symbol, hours=24, as_of=as_of)
        scores = [
            h.ticker_sentiment_score
            for h in headlines
            if h.ticker_sentiment_score is not None
        ]
        if not scores:
            return 0.5
        avg = sum(scores) / len(scores)
        return min(max((1.0 + avg) / 2.0, 0.0), 1.0)
    except Exception:
        logger.warning("Sentiment score failed for %s", symbol, exc_info=True)
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
    *,
    as_of: date | None = None,
) -> float:
    """Put/call open interest ratio as a proxy for institutional flow.

    High put OI relative to call OI suggests institutional hedging,
    which implies support for the stock. Higher ratio = higher score.

    POC simplification: uses the same expiry chain that the trade is from.
    """
    try:
        chain = options_provider.get_options_chain(
            trade.symbol, trade.expiry.isoformat(), as_of=as_of
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
