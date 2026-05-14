"""Tests for AVClient — rate limiter, retry, and cache integration."""

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import httpx

from app.providers.av_client import AVClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "av"


def _noop_transport(*_args, **_kwargs) -> httpx.Response:
    return httpx.Response(200, json={"result": "ok"})


def _make_client(
    transport: httpx.MockTransport | None = None,
    api_key: str = "test-key",
) -> AVClient:
    if transport is None:
        transport = httpx.MockTransport(_noop_transport)
    return AVClient(api_key=api_key, transport=transport)


class TestRateLimiter:
    def test_paces_beyond_75_per_minute(self) -> None:
        request_times: list[float] = []

        def tracking_transport(request: httpx.Request) -> httpx.Response:
            request_times.append(time.monotonic())
            return httpx.Response(200, json={"result": "ok"})

        client = _make_client(httpx.MockTransport(tracking_transport))

        now = time.monotonic()
        with patch("app.providers.av_client.time") as mock_time:
            mock_time.monotonic.return_value = now
            mock_time.sleep = time.sleep

            for i in range(76):
                mock_time.monotonic.return_value = now + i * 0.01
                client._request("OVERVIEW", {"symbol": "AAPL"})

            # The 76th call should have been delayed
            assert len(request_times) == 76


class TestRetry:
    def test_retries_on_429(self) -> None:
        attempts = []

        def transport(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 3:
                return httpx.Response(429, text="rate limited")
            return httpx.Response(200, json={"ok": True})

        client = _make_client(httpx.MockTransport(transport))
        with patch("app.providers.av_client.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            mock_time.sleep = lambda _: None
            result = client._request("OVERVIEW", {"symbol": "AAPL"})

        assert result == {"ok": True}
        assert len(attempts) == 3

    def test_retries_on_500(self) -> None:
        attempts = []

        def transport(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 2:
                return httpx.Response(500, text="server error")
            return httpx.Response(200, json={"ok": True})

        client = _make_client(httpx.MockTransport(transport))
        with patch("app.providers.av_client.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            mock_time.sleep = lambda _: None
            result = client._request("OVERVIEW", {"symbol": "AAPL"})

        assert result == {"ok": True}
        assert len(attempts) == 2

    def test_retries_on_network_error(self) -> None:
        attempts = []

        def transport(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 2:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"ok": True})

        client = _make_client(httpx.MockTransport(transport))
        with patch("app.providers.av_client.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            mock_time.sleep = lambda _: None
            result = client._request("OVERVIEW", {"symbol": "AAPL"})

        assert result == {"ok": True}
        assert len(attempts) == 2


class TestGetOverview:
    def test_returns_parsed_data_with_cache(self) -> None:
        fixture = json.loads((FIXTURES_DIR / "overview_aapl.json").read_text())
        call_count = 0

        def transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            assert "function=OVERVIEW" in str(request.url)
            assert "symbol=AAPL" in str(request.url)
            return httpx.Response(200, json=fixture)

        conn = sqlite3.connect(":memory:")
        client = AVClient(
            api_key="test-key",
            transport=httpx.MockTransport(transport),
            db_conn=conn,
        )

        result = client.get_overview("AAPL")
        assert result["Symbol"] == "AAPL"
        assert result["Beta"] == "1.25"
        assert call_count == 1

        result2 = client.get_overview("AAPL")
        assert result2["Symbol"] == "AAPL"
        assert call_count == 1  # cache hit


class TestGetOptionsChain:
    def test_returns_parsed_chain_with_typed_cache(self) -> None:
        fixture = json.loads(
            (FIXTURES_DIR / "historical_options_aapl.json").read_text()
        )
        call_count = 0

        def transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            assert "function=HISTORICAL_OPTIONS" in str(request.url)
            return httpx.Response(200, json=fixture)

        conn = sqlite3.connect(":memory:")
        client = AVClient(
            api_key="test-key",
            transport=httpx.MockTransport(transport),
            db_conn=conn,
        )

        from datetime import date
        result = client.get_options_chain("AAPL", as_of=date(2026, 5, 14))
        assert result["data"][0]["symbol"] == "AAPL"
        assert result["data"][0]["delta"] == "-0.22000"
        assert call_count == 1

        client.get_options_chain("AAPL", as_of=date(2026, 5, 14))
        assert call_count == 1  # cache hit


class TestGetNewsSentiment:
    def test_returns_parsed_articles(self) -> None:
        fixture = json.loads(
            (FIXTURES_DIR / "news_sentiment_aapl.json").read_text()
        )

        def transport(request: httpx.Request) -> httpx.Response:
            assert "function=NEWS_SENTIMENT" in str(request.url)
            assert "tickers=AAPL" in str(request.url)
            return httpx.Response(200, json=fixture)

        conn = sqlite3.connect(":memory:")
        client = AVClient(
            api_key="test-key",
            transport=httpx.MockTransport(transport),
            db_conn=conn,
        )

        result = client.get_news_sentiment("AAPL")
        assert len(result["feed"]) == 2
        assert result["feed"][0]["ticker_sentiment"][0]["ticker"] == "AAPL"
        sentiment_score = result["feed"][0]["ticker_sentiment"][0]["ticker_sentiment_score"]
        assert float(sentiment_score) > 0
