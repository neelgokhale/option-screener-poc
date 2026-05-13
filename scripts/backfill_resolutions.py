"""Backfill trade resolutions using settlement prices from Alpha Vantage.

Reads settlement_prices.json, resolves all matching unresolved trades
in the SQLite DB, and prints a summary.

Usage:
    python scripts/backfill_resolutions.py
"""

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so `app` imports work
# when running as `python scripts/backfill_resolutions.py`
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.config import settings  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.scoring import compute_pnl  # noqa: E402

PRICES_FILE = Path(__file__).parent / "settlement_prices.json"


def main() -> None:
    # Load settlement prices
    if not PRICES_FILE.exists():
        print(f"Error: {PRICES_FILE} not found. Run fetch_settlement_prices.py first.")
        sys.exit(1)

    with open(PRICES_FILE) as f:
        prices: dict[str, dict[str, float]] = json.load(f)

    # Build a flat lookup: (symbol, expiry) -> close_price
    lookup: dict[tuple[str, str], float] = {}
    for date_str, symbols in prices.items():
        for symbol, close in symbols.items():
            lookup[(symbol, date_str)] = close

    print(f"Loaded {len(lookup)} settlement prices")

    # Connect to DB
    conn = get_connection(settings.db_path)

    # Fetch all unresolved trades
    rows = conn.execute("""
        SELECT id, symbol, expiry, strike, premium
        FROM snapshot_trades
        WHERE outcome IS NULL
    """).fetchall()

    print(f"Found {len(rows)} unresolved trades\n")

    resolved = 0
    skipped = 0
    results: list[dict] = []

    for row in rows:
        trade_id = row["id"]
        symbol = row["symbol"]
        expiry = row["expiry"]
        strike = row["strike"]
        premium = row["premium"]

        settlement = lookup.get((symbol, expiry))
        if settlement is None:
            print(f"  SKIP trade #{trade_id} {symbol} exp {expiry} — no settlement price")
            skipped += 1
            continue

        outcome, pnl_pct = compute_pnl(strike, premium, settlement)

        conn.execute(
            """
            UPDATE snapshot_trades
            SET outcome = ?, settlement_price = ?, pnl_pct = ?
            WHERE id = ?
            """,
            (outcome, settlement, pnl_pct, trade_id),
        )

        results.append({
            "id": trade_id,
            "symbol": symbol,
            "expiry": expiry,
            "strike": strike,
            "premium": premium,
            "settlement": settlement,
            "outcome": outcome,
            "pnl_pct": round(pnl_pct, 4),
        })

        tag = "WIN" if outcome == "OTM" else "LOSS"
        print(f"  #{trade_id:>2} {symbol:<5} strike={strike:<8} settlement={settlement:<10} → {tag} ({pnl_pct:+.2f}%)")
        resolved += 1

    conn.commit()
    conn.close()

    # Summary
    wins = [r for r in results if r["outcome"] == "OTM"]
    losses = [r for r in results if r["outcome"] == "ITM"]

    print(f"\n{'='*60}")
    print(f"Resolved: {resolved}  |  Skipped: {skipped}")
    print(f"Wins (OTM): {len(wins)}  |  Losses (ITM): {len(losses)}")
    if results:
        hit_rate = len(wins) / len(results) * 100
        avg_pnl = sum(r["pnl_pct"] for r in results) / len(results)
        print(f"Hit rate: {hit_rate:.1f}%  |  Avg P&L: {avg_pnl:+.2f}%")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
