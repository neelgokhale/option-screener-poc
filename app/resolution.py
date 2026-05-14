"""Expiry resolution — resolve expired trades and compute outcomes."""

import sqlite3
from collections.abc import Callable
from datetime import date

from app.db import get_unresolved_trades, update_trade_outcome
from app.scoring import compute_pnl


def resolve_expired_trades(
    conn: sqlite3.Connection,
    settlement_price_fn: Callable[[str, str], float | None],
    as_of_date: date | None = None,
) -> int:
    """Resolve all expired, unresolved trades.

    Fetches settlement prices via settlement_price_fn(symbol, expiry_date_str),
    computes outcome and P&L, and updates each trade in the database.

    Returns the number of trades resolved.
    """
    if as_of_date is None:
        as_of_date = date.today()

    trades = get_unresolved_trades(conn, as_of_date)
    resolved = 0

    for trade in trades:
        price = settlement_price_fn(trade["symbol"], trade["expiry"])
        if price is None:
            continue

        outcome, pnl_pct = compute_pnl(trade["strike"], trade["premium"], price)
        update_trade_outcome(conn, trade["id"], outcome, price, pnl_pct)
        resolved += 1

    return resolved
