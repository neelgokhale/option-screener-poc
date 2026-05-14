"""Pydantic models for the backtesting report API."""

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_tracked: int
    total_resolved: int
    total_active: int
    hit_rate: float | None
    avg_return_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    win_loss_ratio: float | None
    date_range_start: str | None
    date_range_end: str | None


class TradeItem(BaseModel):
    id: int
    snapshot_id: int
    snapshot_date: str
    rank: int
    symbol: str
    expiry: str
    strike: float
    premium: float
    pop: float
    delta: float
    theta: float | None
    implied_volatility: float
    expected_value: float
    days_to_expiry: int
    support_level: float
    current_price: float
    premium_yield: float
    open_interest: int
    safety_score: float | None
    adjusted_score: float | None
    next_earnings: str | None
    outcome: str | None
    settlement_price: float | None
    pnl_pct: float | None
    days_remaining: int | None


class TradesResponse(BaseModel):
    trades: list[TradeItem]
