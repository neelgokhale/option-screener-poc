"""Cron entry point — run the daily snapshot workflow.

Usage: python cron.py
"""

import logging

from app.config import settings
from app.db import get_connection
from app.orchestrator import snapshot_daily_trades
from app.providers.yahoo import YahooFinanceProvider, get_settlement_price
from app.resolution import resolve_expired_trades

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    provider = YahooFinanceProvider()
    conn = get_connection(settings.db_path)
    try:
        resolved = resolve_expired_trades(conn, get_settlement_price)
        logger.info("Resolved %d expired trades", resolved)

        snapshot_id = snapshot_daily_trades(conn, provider, provider)
        if snapshot_id is None:
            logger.info("Snapshot already exists for today — skipping")
        else:
            logger.info("Snapshot %d created", snapshot_id)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
