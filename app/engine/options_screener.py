"""Options chain screening engine.

Filters raw options chains against the PRD criteria (§3.4) to find
qualifying short-put candidates. For each stock that passed the universe
filter, this module:

1. Gets available expiry dates
2. Filters to expiries 14-21 days out
3. Fetches the put options chain for qualifying expiries
4. Applies per-contract filters: delta, POP, premium yield, OI, support
5. Calculates EV for passing contracts
6. Returns only EV-positive trades as ScreenedTrade objects

The screener uses delta as a proxy for probability since yfinance doesn't
reliably provide greeks. When delta is unavailable, we estimate it from
the option's moneyness and IV using a simplified Black-Scholes delta
approximation.
"""

import logging
import math
from datetime import date, timedelta

from app.engine.ev_calculator import (
    calculate_ev,
    calculate_expected_loss,
    calculate_pop,
    calculate_premium_yield,
)
from app.engine.technicals import find_support_level
from app.models.option import OptionContract, ScreenedTrade
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, OptionsDataProvider

logger = logging.getLogger(__name__)

# PRD §3.4 screening thresholds
MIN_DTE = 14
MAX_DTE = 21
MIN_DELTA = -0.30  # Most aggressive (higher risk)
MAX_DELTA = -0.15  # Most conservative (lower risk)
MIN_POP = 0.70  # 70%
MIN_PREMIUM_YIELD = 0.005  # 0.5% annualized
MIN_OPEN_INTEREST = 1000
FALLBACK_SUPPORT_DISCOUNT = 0.95  # 5% below current price if no support found


def screen_options_for_stock(
    stock: StockProfile,
    market_provider: MarketDataProvider,
    options_provider: OptionsDataProvider,
) -> list[ScreenedTrade]:
    """Screen all qualifying put options for a single stock.

    Returns a list of ScreenedTrade objects for contracts that pass
    all filters. May return an empty list if no contracts qualify.
    """
    today = date.today()
    target_min = today + timedelta(days=MIN_DTE)
    target_max = today + timedelta(days=MAX_DTE)

    # Get available expiry dates
    try:
        expiry_dates = options_provider.get_expiry_dates(stock.symbol)
    except Exception:
        logger.warning("Failed to get expiry dates for %s", stock.symbol, exc_info=True)
        return []

    # Filter to expiries in our target window
    qualifying_expiries = _filter_expiries(expiry_dates, target_min, target_max)
    if not qualifying_expiries:
        return []

    # Find support level for strike validation
    support = find_support_level(
        market_provider, stock.symbol, stock.current_price
    )
    if support is None:
        support = stock.current_price * FALLBACK_SUPPORT_DISCOUNT

    # Screen puts for each qualifying expiry
    trades: list[ScreenedTrade] = []
    for expiry_str in qualifying_expiries:
        try:
            chain = options_provider.get_options_chain(stock.symbol, expiry_str)
        except Exception:
            logger.warning(
                "Failed to get options chain for %s exp %s",
                stock.symbol, expiry_str, exc_info=True,
            )
            continue

        expiry_date = date.fromisoformat(expiry_str)
        dte = (expiry_date - today).days

        for put in chain.puts:
            trade = _evaluate_put(put, stock, support, dte, expiry_date)
            if trade is not None:
                trades.append(trade)

    return trades


def _filter_expiries(
    expiry_dates: list[str],
    target_min: date,
    target_max: date,
) -> list[str]:
    """Keep only expiry dates within the 14-21 day window."""
    result = []
    for exp_str in expiry_dates:
        try:
            exp_date = date.fromisoformat(exp_str)
            if target_min <= exp_date <= target_max:
                result.append(exp_str)
        except ValueError:
            continue
    return result


def _evaluate_put(
    put: OptionContract,
    stock: StockProfile,
    support: float,
    dte: int,
    expiry_date: date,
) -> ScreenedTrade | None:
    """Apply all screening filters to a single put contract.

    Returns a ScreenedTrade if the contract passes, None otherwise.
    Each filter is checked in order of cheapness (simple checks first,
    expensive calculations last).
    """
    # Filter: open interest (skip filter if OI data is missing, i.e. 0)
    # yfinance often returns 0 OI after hours or for newer expiries
    if put.open_interest > 0 and put.open_interest < MIN_OPEN_INTEREST:
        return None

    # Filter: strike must be below support (out of the money, below key level)
    if put.strike >= support:
        return None

    # Get or estimate delta
    delta = put.delta
    if delta is None:
        delta = _estimate_delta(
            stock.current_price, put.strike, put.implied_volatility, dte
        )

    # Filter: delta range (-0.30 to -0.15)
    if not (MIN_DELTA <= delta <= MAX_DELTA):
        return None

    # Calculate mid price — fall back to lastPrice when market is closed
    # (bid/ask are 0 after hours, but lastPrice retains the last traded value)
    mid_price = (put.bid + put.ask) / 2.0
    if mid_price <= 0:
        mid_price = put.last_price
    if mid_price <= 0:
        return None

    # Filter: POP
    pop = calculate_pop(delta)
    if pop < MIN_POP:
        return None

    # Filter: premium yield
    premium_yield = calculate_premium_yield(mid_price, put.strike, dte)
    if premium_yield < MIN_PREMIUM_YIELD:
        return None

    # Calculate EV
    expected_loss = calculate_expected_loss(put.strike, support)
    ev = calculate_ev(pop, mid_price, expected_loss)

    # Filter: EV must be positive
    if ev <= 0:
        return None

    return ScreenedTrade(
        symbol=stock.symbol,
        expiry=expiry_date,
        strike=put.strike,
        bid=put.bid,
        ask=put.ask,
        mid_price=mid_price,
        delta=delta,
        theta=put.theta,
        implied_volatility=put.implied_volatility,
        open_interest=put.open_interest,
        volume=put.volume,
        current_price=stock.current_price,
        support_level=support,
        days_to_expiry=dte,
        pop=pop,
        premium_yield=premium_yield,
        expected_value=ev,
        expected_loss=expected_loss,
    )


def _estimate_delta(
    spot: float,
    strike: float,
    iv: float,
    dte: int,
) -> float:
    """Estimate put delta when the provider doesn't supply greeks.

    Uses a simplified Black-Scholes delta approximation:
        d1 = (ln(S/K) + 0.5 * σ² * T) / (σ * √T)
        put_delta = N(d1) - 1

    Where N() is the standard normal CDF. We assume risk-free rate ≈ 0
    for simplicity (short-dated options, minimal impact).
    """
    if iv <= 0 or dte <= 0 or spot <= 0 or strike <= 0:
        return 0.0

    t = dte / 365.0
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * t) / (iv * sqrt_t)

    # Standard normal CDF approximation
    nd1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))

    # Put delta = N(d1) - 1
    return nd1 - 1.0
