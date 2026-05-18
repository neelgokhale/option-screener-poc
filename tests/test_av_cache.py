"""Tests for the AVCache — SQLite-backed cache with TTL and stale-on-error."""

import sqlite3
import time
from unittest.mock import patch

from app.providers.av_cache import AVCache


def _make_cache() -> AVCache:
    conn = sqlite3.connect(":memory:")
    return AVCache(conn)


class TestCacheMiss:
    def test_miss_calls_fetcher_and_stores(self) -> None:
        cache = _make_cache()
        call_count = 0

        def fetcher() -> dict:
            nonlocal call_count
            call_count += 1
            return {"symbol": "AAPL", "Beta": "1.2"}

        result = cache.get_or_fetch("overview:AAPL", ttl_seconds=3600, fetcher=fetcher)
        assert result == {"symbol": "AAPL", "Beta": "1.2"}
        assert call_count == 1

        result2 = cache.get_or_fetch("overview:AAPL", ttl_seconds=3600, fetcher=fetcher)
        assert result2 == {"symbol": "AAPL", "Beta": "1.2"}
        assert call_count == 1  # fetcher not called again


class TestCacheHit:
    def test_hit_within_ttl_skips_fetcher(self) -> None:
        cache = _make_cache()
        call_count = 0

        def fetcher() -> dict:
            nonlocal call_count
            call_count += 1
            return {"price": 150.0}

        cache.get_or_fetch("price:AAPL", ttl_seconds=3600, fetcher=fetcher)
        assert call_count == 1

        result = cache.get_or_fetch("price:AAPL", ttl_seconds=3600, fetcher=fetcher)
        assert result == {"price": 150.0}
        assert call_count == 1


class TestCacheExpiry:
    def test_expired_entry_re_fetches(self) -> None:
        cache = _make_cache()
        call_count = 0
        current_value = {"v": 1}

        def fetcher() -> dict:
            nonlocal call_count
            call_count += 1
            return current_value

        now = time.time()
        with patch("app.providers.av_cache.time") as mock_time:
            mock_time.time.return_value = now
            cache.get_or_fetch("key", ttl_seconds=60, fetcher=fetcher)
            assert call_count == 1

            mock_time.time.return_value = now + 61
            current_value = {"v": 2}
            result = cache.get_or_fetch("key", ttl_seconds=60, fetcher=fetcher)
            assert result == {"v": 2}
            assert call_count == 2


class TestStaleOnError:
    def test_serves_stale_on_fetcher_failure(self, caplog) -> None:
        cache = _make_cache()

        cache.get_or_fetch("key", ttl_seconds=60, fetcher=lambda: {"v": 1})

        now = time.time()
        with patch("app.providers.av_cache.time") as mock_time:
            mock_time.time.return_value = now + 120

            def failing_fetcher():
                raise ConnectionError("AV down")

            import logging
            with caplog.at_level(logging.WARNING, logger="app.providers.av_cache"):
                result = cache.get_or_fetch("key", ttl_seconds=60, fetcher=failing_fetcher)

            assert result == {"v": 1}
            assert "stale" in caplog.text.lower()

    def test_no_stale_entry_propagates_error(self) -> None:
        cache = _make_cache()

        def failing_fetcher():
            raise ConnectionError("AV down")

        try:
            cache.get_or_fetch("key", ttl_seconds=60, fetcher=failing_fetcher)
            assert False, "Should have raised"
        except ConnectionError:
            pass


class TestBypassCache:
    def test_bypass_always_calls_fetcher(self) -> None:
        cache = _make_cache()
        call_count = 0

        def fetcher() -> dict:
            nonlocal call_count
            call_count += 1
            return {"v": call_count}

        cache.get_or_fetch("key", ttl_seconds=3600, fetcher=fetcher)
        assert call_count == 1

        result = cache.get_or_fetch(
            "key", ttl_seconds=3600, fetcher=fetcher, bypass_cache=True
        )
        assert call_count == 2
        assert result == {"v": 2}

        result3 = cache.get_or_fetch("key", ttl_seconds=3600, fetcher=fetcher)
        assert call_count == 2  # normal hit uses updated cache
        assert result3 == {"v": 2}


class TestOptionsChainCache:
    def test_store_and_retrieve_chain(self) -> None:
        cache = _make_cache()
        contracts = [
            {
                "symbol": "AAPL",
                "expiration": "2026-06-20",
                "strike": 200.0,
                "option_type": "put",
                "bid": 2.50,
                "ask": 2.70,
                "last_price": 2.60,
                "mark": 2.60,
                "volume": 1500,
                "open_interest": 8000,
                "implied_volatility": 0.25,
                "delta": -0.22,
                "gamma": 0.015,
                "theta": -0.05,
                "vega": 0.10,
                "rho": -0.01,
            },
            {
                "symbol": "AAPL",
                "expiration": "2026-06-20",
                "strike": 195.0,
                "option_type": "put",
                "bid": 1.80,
                "ask": 2.00,
                "last_price": 1.90,
                "mark": 1.90,
                "volume": 900,
                "open_interest": 5000,
                "implied_volatility": 0.23,
                "delta": -0.18,
                "gamma": 0.012,
                "theta": -0.04,
                "vega": 0.08,
                "rho": -0.008,
            },
        ]

        cache.store_options_chain("AAPL", "2026-05-14", contracts)
        result = cache.get_options_chain("AAPL", "2026-05-14")

        assert len(result) == 2
        assert result[0]["strike"] == 195.0
        assert result[0]["delta"] == -0.18
        assert result[1]["strike"] == 200.0
        assert result[1]["delta"] == -0.22

    def test_get_missing_chain_returns_none(self) -> None:
        cache = _make_cache()
        result = cache.get_options_chain("AAPL", "2026-05-14")
        assert result is None
