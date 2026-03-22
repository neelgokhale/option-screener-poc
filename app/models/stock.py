from pydantic import BaseModel


class StockProfile(BaseModel):
    """Fundamental data for a single stock, used for universe filtering."""

    symbol: str
    name: str
    sector: str
    market_cap: float  # USD
    net_income: float  # USD, trailing twelve months
    roe: float  # Return on equity as decimal (e.g., 0.15 = 15%)
    debt_to_ebitda: float  # Total debt / EBITDA
    avg_volume: float  # Average daily volume in shares
    current_price: float
    previous_close: float
    pre_market_price: float | None = None  # None if not available


class UniverseFilterResult(BaseModel):
    """Result of running the stock universe filter."""

    qualified: list[str]  # Symbols that passed all filters
    total_scanned: int
    filtered_out: dict[str, list[str]]  # reason -> list of symbols excluded
