"""SQLite-backed cache with TTL and stale-on-error semantics for AV data."""

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class AVCache:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._create_tables()

    def get_or_fetch(
        self,
        key: str,
        ttl_seconds: int,
        fetcher: Callable[[], Any],
        *,
        bypass_cache: bool = False,
    ) -> Any:
        stale_payload: str | None = None

        if not bypass_cache:
            row = self._conn.execute(
                "SELECT payload, cached_at FROM av_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is not None:
                cached_at = row[1]
                if time.time() - cached_at < ttl_seconds:
                    return json.loads(row[0])
                stale_payload = row[0]

        try:
            result = fetcher()
        except Exception:
            if stale_payload is not None:
                logger.warning("Fetch failed for %s, serving stale cache entry", key)
                return json.loads(stale_payload)
            raise

        self._conn.execute(
            """INSERT OR REPLACE INTO av_cache (cache_key, payload, cached_at)
               VALUES (?, ?, ?)""",
            (key, json.dumps(result), time.time()),
        )
        self._conn.commit()
        return result

    def store_options_chain(
        self, symbol: str, as_of_date: str, contracts: list[dict]
    ) -> None:
        now = time.time()
        self._conn.executemany(
            """INSERT OR REPLACE INTO av_options_chain_cache
               (symbol, as_of_date, expiration, strike, option_type,
                bid, ask, last_price, mark, volume, open_interest,
                implied_volatility, delta, gamma, theta, vega, rho, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    symbol, as_of_date, c["expiration"], c["strike"], c["option_type"],
                    c.get("bid"), c.get("ask"), c.get("last_price"), c.get("mark"),
                    c.get("volume"), c.get("open_interest"),
                    c.get("implied_volatility"), c.get("delta"), c.get("gamma"),
                    c.get("theta"), c.get("vega"), c.get("rho"), now,
                )
                for c in contracts
            ],
        )
        self._conn.commit()

    def get_options_chain(self, symbol: str, as_of_date: str) -> list[dict] | None:
        rows = self._conn.execute(
            """SELECT expiration, strike, option_type, bid, ask, last_price,
                      mark, volume, open_interest, implied_volatility,
                      delta, gamma, theta, vega, rho
               FROM av_options_chain_cache
               WHERE symbol = ? AND as_of_date = ?
               ORDER BY expiration, strike""",
            (symbol, as_of_date),
        ).fetchall()
        if not rows:
            return None
        columns = [
            "expiration", "strike", "option_type", "bid", "ask", "last_price",
            "mark", "volume", "open_interest", "implied_volatility",
            "delta", "gamma", "theta", "vega", "rho",
        ]
        return [dict(zip(columns, row)) for row in rows]

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS av_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                cached_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS av_options_chain_cache (
                symbol TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                expiration TEXT NOT NULL,
                strike REAL NOT NULL,
                option_type TEXT NOT NULL,
                bid REAL,
                ask REAL,
                last_price REAL,
                mark REAL,
                volume INTEGER,
                open_interest INTEGER,
                implied_volatility REAL,
                delta REAL,
                gamma REAL,
                theta REAL,
                vega REAL,
                rho REAL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (symbol, as_of_date, expiration, strike, option_type)
            );
        """)
