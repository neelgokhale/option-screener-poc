from pydantic import BaseModel


class MarketRiskStatus(BaseModel):
    """Current market risk indicators."""

    vix_level: float
    vix_threshold: float = 25.0
    spy_price: float
    spy_sma_20: float
    spy_above_sma: bool
    risk_elevated: bool  # True if VIX > threshold or SPY below SMA
    risk_reason: str | None = None  # Human-readable explanation
