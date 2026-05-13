"""Fetch settlement prices from Alpha Vantage for trade resolution backfill.

Loops through unique (symbol, expiry) pairs from unresolved trades,
fetches daily close prices via TIME_SERIES_DAILY, and writes
the results to settlement_prices.json.

Usage:
    export ALPHAVANTAGE_API_KEY=your_key
    python scripts/fetch_settlement_prices.py
"""

import json
import os
import sys
import time

import httpx

API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")
BASE_URL = "https://www.alphavantage.co/query"
OUTPUT_FILE = "scripts/settlement_prices.json"

# (symbol, [expiry_dates]) — derived from the 46 unresolved trades
SYMBOL_DATES: dict[str, list[str]] = {
    "AAPL": ["2026-04-24"],
    "AMZN": ["2026-04-24"],
    "BBY":  ["2026-05-01"],
    "MSFT": ["2026-04-24"],
    "MU":   ["2026-04-24"],
    "NFLX": ["2026-05-08"],
    "NKE":  ["2026-04-24", "2026-05-01"],
    "NVDA": ["2026-04-24", "2026-05-01"],
    "PLTR": ["2026-04-24", "2026-05-01"],
    "TPR":  ["2026-05-01"],
    "UBER": ["2026-05-01"],
    "WMT":  ["2026-04-24", "2026-05-01", "2026-05-08"],
}

# Alpha Vantage free tier: 25 requests/day, 5/min
RATE_LIMIT_SLEEP = 5  # seconds between calls to stay under 5/min


def fetch_daily_close(symbol: str, client: httpx.Client) -> dict[str, float]:
    """Fetch TIME_SERIES_DAILY for a symbol, return {date: close_price}."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": API_KEY,
    }
    resp = client.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "Error Message" in data:
        print(f"  ERROR: {data['Error Message']}")
        return {}

    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information")
        print(f"  RATE LIMITED: {msg}")
        return {}

    time_series = data.get("Time Series (Daily)", {})
    return {
        date_str: float(values["4. close"])
        for date_str, values in time_series.items()
    }


def main() -> None:
    if not API_KEY:
        print("Error: set ALPHAVANTAGE_API_KEY environment variable")
        sys.exit(1)

    results: dict[str, dict[str, float]] = {}
    # {expiry_date: {symbol: close_price}}

    symbols = sorted(SYMBOL_DATES.keys())
    total = len(symbols)

    with httpx.Client(timeout=30) as client:
        for i, symbol in enumerate(symbols, 1):
            needed_dates = SYMBOL_DATES[symbol]
            print(f"[{i}/{total}] Fetching {symbol} (need dates: {needed_dates})")

            daily_data = fetch_daily_close(symbol, client)

            if not daily_data:
                print(f"  No data returned for {symbol}")
                continue

            for target_date in needed_dates:
                close = daily_data.get(target_date)
                if close is not None:
                    results.setdefault(target_date, {})[symbol] = close
                    print(f"  {target_date}: ${close:.2f}")
                else:
                    print(f"  {target_date}: NOT FOUND in response")

            # Rate limit — skip sleep after last symbol
            if i < total:
                print(f"  Sleeping {RATE_LIMIT_SLEEP}s (rate limit)...")
                time.sleep(RATE_LIMIT_SLEEP)

    # Write results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print(f"\nDone. Wrote {OUTPUT_FILE}")
    print(f"Settlement prices found: {sum(len(v) for v in results.values())}/17")


if __name__ == "__main__":
    main()
