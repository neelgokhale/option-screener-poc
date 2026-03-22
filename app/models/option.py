from datetime import date

from pydantic import BaseModel


class OptionContract(BaseModel):
    """Raw option contract data from a provider."""

    symbol: str
    expiry: date
    strike: float
    option_type: str  # "put" or "call"
    bid: float
    ask: float
    last_price: float
    delta: float | None = None
    theta: float | None = None
    gamma: float | None = None
    implied_volatility: float
    open_interest: int
    volume: int


class OptionsChain(BaseModel):
    """Full options chain for a symbol and expiry."""

    symbol: str
    expiry: date
    puts: list[OptionContract]
    calls: list[OptionContract]


class ScreenedTrade(BaseModel):
    """A put option that passed all screening criteria.

    This is the output of the options screener before safety scoring.
    It enriches the raw OptionContract with computed metrics like POP,
    premium yield, EV, and the support level used for screening.
    """

    symbol: str
    expiry: date
    strike: float
    bid: float
    ask: float
    mid_price: float  # (bid + ask) / 2
    delta: float
    theta: float | None = None
    implied_volatility: float
    open_interest: int
    volume: int
    current_price: float
    support_level: float
    days_to_expiry: int
    pop: float  # Probability of profit (1 - |delta|)
    premium_yield: float  # Annualized: (mid / strike) * (365 / DTE)
    expected_value: float  # EV per contract
    expected_loss: float  # Max loss if stock drops to support


class TradeOutput(BaseModel):
    """Final ranked trade ready for the API response.

    Extends ScreenedTrade with ranking and earnings info.
    Safety score fields are None until Phase 3 adds them.
    """

    rank: int
    symbol: str
    expiry: date
    strike: float
    premium: float  # mid_price
    pop: float
    delta: float
    theta: float | None = None
    implied_volatility: float
    expected_value: float
    days_to_expiry: int
    support_level: float
    current_price: float
    premium_yield: float
    open_interest: int
    safety_score: float | None = None
    adjusted_score: float | None = None
    next_earnings: date | None = None


class ScanResult(BaseModel):
    """Full result from a pipeline scan."""

    trades: list[TradeOutput]
    universe_size: int
    qualified_stocks: int
    trades_screened: int
    scan_timestamp: str


class Headline(BaseModel):
    """A news headline for risk filtering."""

    title: str
    source: str
    published_at: str
    url: str | None = None
