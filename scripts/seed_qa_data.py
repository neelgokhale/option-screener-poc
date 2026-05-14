"""Seed the local SQLite DB with realistic test data for QA.

Usage: uv run python scripts/seed_qa_data.py
"""

from app.db import get_connection, insert_snapshot, insert_trades, update_trade_outcome

DB_PATH = "data/screener.db"


def main() -> None:
    conn = get_connection(DB_PATH)

    # Snapshot 1 — older, all trades resolved
    s1 = insert_snapshot(conn, {
        "snapshot_date": "2026-03-15",
        "universe_size": 500,
        "qualified_stocks": 42,
        "trades_screened": 180,
        "market_risk_elevated": 0,
        "vix_level": 14.2,
        "spy_price": 525.0,
    })

    resolved_trades = [
        {"rank": 1, "symbol": "AAPL", "expiry": "2026-03-28", "strike": 170.0,
         "premium": 2.80, "pop": 0.74, "delta": -0.26, "theta": 0.05,
         "implied_volatility": 0.28, "expected_value": 2.07, "days_to_expiry": 13,
         "support_level": 168.0, "current_price": 178.50, "premium_yield": 1.65,
         "open_interest": 1500, "safety_score": 85.0, "adjusted_score": 81.0,
         "next_earnings": "2026-05-01"},
        {"rank": 2, "symbol": "MSFT", "expiry": "2026-03-28", "strike": 400.0,
         "premium": 5.20, "pop": 0.70, "delta": -0.30, "theta": 0.04,
         "implied_volatility": 0.30, "expected_value": 3.64, "days_to_expiry": 13,
         "support_level": 395.0, "current_price": 415.0, "premium_yield": 1.30,
         "open_interest": 900, "safety_score": 78.0, "adjusted_score": 74.0,
         "next_earnings": None},
        {"rank": 3, "symbol": "NVDA", "expiry": "2026-03-28", "strike": 120.0,
         "premium": 3.10, "pop": 0.65, "delta": -0.35, "theta": 0.06,
         "implied_volatility": 0.42, "expected_value": 2.02, "days_to_expiry": 13,
         "support_level": 118.0, "current_price": 130.0, "premium_yield": 2.58,
         "open_interest": 2200, "safety_score": 68.0, "adjusted_score": 62.0,
         "next_earnings": "2026-05-15"},
    ]
    insert_trades(conn, s1, resolved_trades)

    # Resolve them: AAPL OTM win, MSFT OTM win, NVDA ITM loss
    update_trade_outcome(conn, 1, "OTM", 175.0, 1.65)
    update_trade_outcome(conn, 2, "OTM", 408.0, 1.30)
    update_trade_outcome(conn, 3, "ITM", 112.0, -4.08)

    # Snapshot 2 — recent, trades still active
    s2 = insert_snapshot(conn, {
        "snapshot_date": "2026-04-01",
        "universe_size": 500,
        "qualified_stocks": 38,
        "trades_screened": 165,
        "market_risk_elevated": 0,
        "vix_level": 15.8,
        "spy_price": 530.0,
    })

    active_trades = [
        {"rank": 1, "symbol": "GOOGL", "expiry": "2026-04-18", "strike": 165.0,
         "premium": 3.40, "pop": 0.72, "delta": -0.28, "theta": 0.04,
         "implied_volatility": 0.31, "expected_value": 2.45, "days_to_expiry": 17,
         "support_level": 162.0, "current_price": 174.0, "premium_yield": 2.06,
         "open_interest": 1100, "safety_score": 80.0, "adjusted_score": 76.0,
         "next_earnings": "2026-04-29"},
        {"rank": 2, "symbol": "AMZN", "expiry": "2026-04-18", "strike": 185.0,
         "premium": 4.10, "pop": 0.69, "delta": -0.31, "theta": 0.05,
         "implied_volatility": 0.34, "expected_value": 2.83, "days_to_expiry": 17,
         "support_level": 182.0, "current_price": 195.0, "premium_yield": 2.22,
         "open_interest": 800, "safety_score": 74.0, "adjusted_score": 70.0,
         "next_earnings": None},
        {"rank": 3, "symbol": "META", "expiry": "2026-04-18", "strike": 520.0,
         "premium": 8.50, "pop": 0.67, "delta": -0.33, "theta": 0.07,
         "implied_volatility": 0.36, "expected_value": 5.70, "days_to_expiry": 17,
         "support_level": 515.0, "current_price": 545.0, "premium_yield": 1.63,
         "open_interest": 650, "safety_score": 71.0, "adjusted_score": 66.0,
         "next_earnings": "2026-04-30"},
    ]
    insert_trades(conn, s2, active_trades)

    conn.close()
    print("Seeded 2 snapshots, 3 resolved trades, 3 active trades")


if __name__ == "__main__":
    main()
