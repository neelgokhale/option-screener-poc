"""Expected Value (EV) calculator for short-put trades.

The EV model determines whether a trade has a positive mathematical edge.
Only EV-positive trades are selected — this is the core quality gate.

Formula (from PRD §3.6):
    EV = (POP × Premium) - ((1 - POP) × Expected Loss)

Where:
    POP = 1 - |delta|  (probability of profit)
    Premium = mid_price × 100  (per contract, 100 shares)
    Expected Loss = (strike - support_level) × 100  (max loss to support)

The expected loss uses the distance from strike to support as the
downside scenario. This is conservative — it assumes that if the trade
goes wrong, the stock drops to support before recovering.
"""


def calculate_pop(delta: float) -> float:
    """Calculate probability of profit from delta.

    POP ≈ 1 - |delta|. For a put with delta -0.25, POP = 75%.
    """
    return 1.0 - abs(delta)


def calculate_premium_yield(mid_price: float, strike: float, dte: int) -> float:
    """Calculate annualized premium yield.

    Yield = (premium / strike) × (365 / DTE)
    This normalizes premium across different strikes and expiries
    so trades can be compared on an apples-to-apples basis.
    """
    if strike <= 0 or dte <= 0:
        return 0.0
    return (mid_price / strike) * (365.0 / dte)


def calculate_expected_loss(strike: float, support_level: float) -> float:
    """Calculate the expected loss per share if the trade goes against us.

    Expected loss = strike - support_level.
    This assumes the worst case is the stock dropping to support.
    Clamped to a minimum of 0 (support above strike shouldn't happen
    but we guard against it).
    """
    return max(0.0, strike - support_level)


def calculate_ev(
    pop: float,
    mid_price: float,
    expected_loss: float,
) -> float:
    """Calculate expected value per contract (100 shares).

    EV = (POP × premium_per_contract) - ((1 - POP) × loss_per_contract)

    A positive EV means the trade has a mathematical edge over many
    repetitions. We only select EV+ trades.
    """
    premium_per_contract = mid_price * 100
    loss_per_contract = expected_loss * 100
    return (pop * premium_per_contract) - ((1.0 - pop) * loss_per_contract)
