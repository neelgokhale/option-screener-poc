"""Tests for AV adapter classes — thin translation layer over AVClient."""

import json
import sqlite3
from datetime import date
from pathlib import Path

import httpx

from app.providers.av_client import AVClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "av"


def _make_av_client(fixture_map: dict[str, str | dict]) -> AVClient:
    """Create an AVClient backed by MockTransport returning fixtures by function name."""
    def transport(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for function_name, fixture in fixture_map.items():
            if f"function={function_name}" in url:
                if isinstance(fixture, str):
                    data = json.loads((FIXTURES_DIR / fixture).read_text())
                else:
                    data = fixture
                return httpx.Response(200, json=data)
        return httpx.Response(404, text="not found")

    conn = sqlite3.connect(":memory:")
    return AVClient(
        api_key="test-key",
        transport=httpx.MockTransport(transport),
        db_conn=conn,
    )


class TestAVMarketDataAdapter:
    def test_get_stock_info_returns_profile_with_beta(self) -> None:
        from app.providers.av_adapters import AVMarketDataAdapter

        client = _make_av_client({
            "OVERVIEW": "overview_aapl.json",
            "BALANCE_SHEET": {
                "symbol": "AAPL",
                "quarterlyReports": [
                    {
                        "fiscalDateEnding": "2026-03-31",
                        "shortLongTermDebtTotal": "120000000000",
                    }
                ],
            },
        })
        adapter = AVMarketDataAdapter(client)

        profile = adapter.get_stock_info("AAPL")
        assert profile is not None
        assert profile.symbol == "AAPL"
        assert profile.name == "Apple Inc"
        assert profile.sector == "TECHNOLOGY"
        assert profile.market_cap == 3_200_000_000_000
        assert profile.roe == 1.50
        assert profile.beta == 1.25
        assert profile.current_price > 0

    def test_get_price_history_returns_dataframe(self) -> None:
        from app.providers.av_adapters import AVMarketDataAdapter

        client = _make_av_client({
            "TIME_SERIES_DAILY_ADJUSTED": "time_series_daily_aapl.json",
        })
        adapter = AVMarketDataAdapter(client)

        df = adapter.get_price_history("AAPL")
        assert not df.empty
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 3
        assert df["Close"].iloc[-1] == 233.50


class TestAVOptionsAdapter:
    def test_get_options_chain_returns_chain_with_greeks(self) -> None:
        from app.providers.av_adapters import AVOptionsAdapter

        client = _make_av_client({
            "HISTORICAL_OPTIONS": "historical_options_aapl.json",
        })
        adapter = AVOptionsAdapter(client)

        chain = adapter.get_options_chain("AAPL", "2026-06-20")
        assert chain.symbol == "AAPL"
        assert chain.expiry == date(2026, 6, 20)
        assert len(chain.puts) == 1
        assert len(chain.calls) == 1
        assert chain.puts[0].delta == -0.22
        assert chain.puts[0].strike == 200.0
        assert chain.puts[0].open_interest == 8000
        assert chain.calls[0].delta == 0.78

    def test_get_expiry_dates_returns_unique_sorted(self) -> None:
        from app.providers.av_adapters import AVOptionsAdapter

        client = _make_av_client({
            "HISTORICAL_OPTIONS": "historical_options_aapl.json",
        })
        adapter = AVOptionsAdapter(client)

        expiries = adapter.get_expiry_dates("AAPL")
        assert expiries == ["2026-06-20"]


class TestAVNewsAdapter:
    def test_get_recent_headlines_returns_headlines(self) -> None:
        from app.providers.av_adapters import AVNewsAdapter

        client = _make_av_client({
            "NEWS_SENTIMENT": "news_sentiment_aapl.json",
        })
        adapter = AVNewsAdapter(client)

        headlines = adapter.get_recent_headlines("AAPL")
        assert len(headlines) == 2
        assert headlines[0].title == "Apple reports record quarterly earnings"
        assert headlines[0].source == "TestNews"
        assert headlines[1].title == "Tech sector faces regulatory pressure"
