"""Cron entry point — run the daily snapshot workflow.

Usage: python cron.py
"""

import logging
from collections.abc import Callable
from datetime import date, timedelta

from app.backup import run_backup
from app.config import settings
from app.db import get_connection
from app.orchestrator import snapshot_daily_trades
from app.providers.av_adapters import AVMarketDataAdapter, AVOptionsAdapter
from app.providers.av_client import AVClient
from app.resolution import resolve_expired_trades

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _av_settlement_price(client: AVClient) -> Callable[[str, str], float | None]:
    def _fetch(symbol: str, expiry_date: str) -> float | None:
        try:
            data = client.get_price_history(symbol)
            ts_key = next((k for k in data if "Time Series" in k), None)
            if ts_key is None:
                return None
            series = data[ts_key]
            expiry = date.fromisoformat(expiry_date)
            for offset in range(4):
                d = (expiry + timedelta(days=offset)).isoformat()
                if d in series:
                    return float(series[d]["4. close"])
            return None
        except Exception:
            logger.warning(
                "Settlement price fetch failed for %s on %s",
                symbol, expiry_date, exc_info=True,
            )
            return None

    return _fetch


def main() -> None:
    client = AVClient(api_key=settings.alphavantage_api_key)
    market = AVMarketDataAdapter(client)
    options = AVOptionsAdapter(client)
    conn = get_connection(settings.db_path)
    try:
        resolved = resolve_expired_trades(conn, _av_settlement_price(client))
        logger.info("Resolved %d expired trades", resolved)

        snapshot_id = snapshot_daily_trades(conn, market, options)
        if snapshot_id is None:
            logger.info("Snapshot already exists for today — skipping")
        else:
            logger.info("Snapshot %d created", snapshot_id)
    finally:
        conn.close()

    run_backup(settings)


if __name__ == "__main__":
    main()
