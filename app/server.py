"""FastAPI application instance and route registration.

This is the main entry point for the backend. Vercel's Python runtime
picks up the `app` object from `api/index.py`, which imports it from here.
For local development, run: uvicorn app.server:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.engine.market_risk import assess_market_risk
from app.engine.pipeline import run_scan
from app.engine.universe import filter_universe
from app.models.market import MarketRiskStatus
from app.models.option import ScanResult
from app.models.stock import UniverseFilterResult
from app.providers.news import FinnhubNewsProvider
from app.providers.yahoo import YahooFinanceProvider

app = FastAPI(
    title="Option Screener API",
    version="0.1.0",
    description="AI Short-Put Option Screener for the wheel strategy",
)

# Allow frontend to call API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared provider instances — created once, reused across requests
_yahoo = YahooFinanceProvider()
_news = FinnhubNewsProvider() if settings.finnhub_api_key else None


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/universe", response_model=UniverseFilterResult)
def get_universe(symbols: str | None = None) -> UniverseFilterResult:
    """Run the stock universe filter and return qualified symbols.

    Query params:
        symbols: Optional comma-separated list of symbols to scan
                 instead of the full S&P 500. Useful for testing.
    """
    symbol_list = symbols.split(",") if symbols else None
    return filter_universe(_yahoo, symbols=symbol_list)


@app.get("/api/trades", response_model=ScanResult)
def get_trades(
    symbols: str | None = None,
    max_trades: int | None = None,
) -> ScanResult:
    """Run the full screening pipeline and return ranked trades.

    Query params:
        symbols: Optional comma-separated list of symbols to scan
                 instead of the full S&P 500. Useful for testing.
        max_trades: Override the default max trades to return.
    """
    symbol_list = symbols.split(",") if symbols else None
    return run_scan(
        market_provider=_yahoo,
        options_provider=_yahoo,
        news_provider=_news,
        symbols=symbol_list,
        max_trades=max_trades,
    )


@app.get("/api/market-status", response_model=MarketRiskStatus)
def get_market_status() -> MarketRiskStatus:
    """Get current market risk indicators (VIX + SPY trend)."""
    return assess_market_risk(_yahoo)
