"""CLI entry point for walk-forward backtesting.

Usage:
    python scripts/run_backtest.py --start 2025-05-01 --end 2025-05-15 --frequency weekly --name smoke-test
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.backtest import BacktestRunner
from app.config import settings
from app.db import get_connection
from app.engine.market_risk import assess_market_risk
from app.engine.pipeline import run_scan
from app.providers.av_adapters import AVMarketDataAdapter, AVNewsAdapter, AVOptionsAdapter
from app.providers.av_client import AVClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a walk-forward backtest")
    parser.add_argument("--start", type=_parse_date, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=_parse_date, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--frequency", default="weekly", choices=["weekly"], help="Scan frequency")
    parser.add_argument("--name", required=True, help="Run name for identification")
    args = parser.parse_args()

    conn = get_connection(settings.db_path)
    client = AVClient(api_key=settings.alphavantage_api_key, db_conn=conn)
    market = AVMarketDataAdapter(client)
    options = AVOptionsAdapter(client)
    news = AVNewsAdapter(client)

    def get_settlement_price(symbol: str, expiry_str: str) -> float | None:
        data = client.get_price_history(symbol)
        ts_key = next((k for k in data if "Time Series" in k), None)
        if ts_key is None:
            return None
        close = data[ts_key].get(expiry_str)
        if close is None:
            for d in sorted(data[ts_key].keys(), reverse=True):
                if d <= expiry_str:
                    close = data[ts_key][d]
                    break
        if close is None:
            return None
        return float(close["4. close"])

    runner = BacktestRunner(
        conn=conn,
        scan_fn=lambda as_of: run_scan(market, options, news, as_of=as_of),
        settlement_price_fn=get_settlement_price,
        market_risk_fn=lambda as_of: assess_market_risk(market, as_of=as_of),
    )

    logger.info("Starting backtest '%s': %s to %s (%s)", args.name, args.start, args.end, args.frequency)
    run_id = runner.run(start=args.start, end=args.end, frequency=args.frequency, name=args.name)
    logger.info("Backtest complete — run_id=%d", run_id)


if __name__ == "__main__":
    main()
