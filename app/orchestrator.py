"""Backtest orchestrator — daily snapshot workflow."""

import sqlite3
from datetime import date

from app.db import insert_snapshot, insert_trades
from app.engine.market_risk import assess_market_risk
from app.engine.pipeline import run_scan
from app.providers.base import MarketDataProvider, NewsProvider, OptionsDataProvider


def snapshot_daily_trades(
    conn: sqlite3.Connection,
    market_provider: MarketDataProvider,
    options_provider: OptionsDataProvider,
    news_provider: NewsProvider | None = None,
    today: date | None = None,
) -> int | None:
    """Run the screener and persist today's snapshot.

    Returns the snapshot ID, or None if today was already snapshotted.
    """
    if today is None:
        today = date.today()

    existing = conn.execute(
        "SELECT id FROM snapshots WHERE snapshot_date = ?", (today.isoformat(),)
    ).fetchone()
    if existing:
        return None

    scan = run_scan(market_provider, options_provider, news_provider)
    market = assess_market_risk(market_provider)

    snapshot = {
        "snapshot_date": today.isoformat(),
        "universe_size": scan.universe_size,
        "qualified_stocks": scan.qualified_stocks,
        "trades_screened": scan.trades_screened,
        "market_risk_elevated": market.risk_elevated,
        "vix_level": market.vix_level,
        "spy_price": market.spy_price,
    }
    snapshot_id = insert_snapshot(conn, snapshot)

    if scan.trades:
        trade_dicts = [
            {
                "rank": t.rank,
                "symbol": t.symbol,
                "expiry": t.expiry.isoformat(),
                "strike": t.strike,
                "premium": t.premium,
                "pop": t.pop,
                "delta": t.delta,
                "theta": t.theta,
                "implied_volatility": t.implied_volatility,
                "expected_value": t.expected_value,
                "days_to_expiry": t.days_to_expiry,
                "support_level": t.support_level,
                "current_price": t.current_price,
                "premium_yield": t.premium_yield,
                "open_interest": t.open_interest,
                "safety_score": t.safety_score,
                "adjusted_score": t.adjusted_score,
                "next_earnings": t.next_earnings.isoformat() if t.next_earnings else None,
            }
            for t in scan.trades
        ]
        insert_trades(conn, snapshot_id, trade_dicts)

    return snapshot_id
