from pydantic import BaseModel


class SafetyComponents(BaseModel):
    """Individual components of the safety score, for transparency."""

    distance_from_support: float  # 0-1, weight 25%
    pre_market_stability: float  # 0-1, weight 15%
    sector_correlation: float  # 0-1, weight 10%
    iv_rank_stability: float  # 0-1, weight 15%
    institutional_flow: float  # 0-1, weight 20%
    market_risk: float  # 0-1, weight 15%


class SafetyResult(BaseModel):
    """Final safety score with component breakdown."""

    score: float  # Weighted composite, 0-1
    components: SafetyComponents
