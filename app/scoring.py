"""Scoring module — pure functions for trade P&L and aggregate statistics."""


def compute_pnl(strike: float, premium: float, settlement_price: float) -> tuple[str, float]:
    """Determine outcome and P&L percentage for a resolved trade.

    Returns (outcome, pnl_pct) where outcome is "OTM" or "ITM".
    """
    if settlement_price > strike:
        return "OTM", premium / strike * 100
    else:
        return "ITM", ((settlement_price - strike) + premium) / strike * 100


def compute_stats(trades: list[dict]) -> dict:
    """Compute aggregate statistics from a list of resolved trades.

    Each trade dict must have 'outcome' ("OTM"/"ITM") and 'pnl_pct' keys.
    """
    if not trades:
        return {
            "hit_rate": None,
            "avg_return_pct": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "win_loss_ratio": None,
        }

    wins = [t for t in trades if t["outcome"] == "OTM"]
    losses = [t for t in trades if t["outcome"] == "ITM"]
    total = len(trades)

    hit_rate = len(wins) / total * 100
    avg_return_pct = sum(t["pnl_pct"] for t in trades) / total

    avg_win_pct = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else None
    avg_loss_pct = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else None

    win_loss_ratio = None
    if avg_win_pct is not None and avg_loss_pct is not None and avg_loss_pct != 0:
        win_loss_ratio = abs(avg_win_pct) / abs(avg_loss_pct)

    return {
        "hit_rate": hit_rate,
        "avg_return_pct": avg_return_pct,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "win_loss_ratio": win_loss_ratio,
    }
