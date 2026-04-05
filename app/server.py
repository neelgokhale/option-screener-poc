"""FastAPI application instance and route registration.

This is the main entry point for the backend.
For local development, run: uvicorn app.server:app --reload
"""

import logging
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import get_connection, get_summary_stats, get_trades_by_status
from app.engine.market_risk import assess_market_risk
from app.engine.pipeline import run_scan
from app.engine.universe import filter_universe
from app.models.market import MarketRiskStatus
from app.models.option import ScanResult
from app.models.report import SummaryResponse, TradeItem, TradesResponse
from app.models.stock import UniverseFilterResult
from app.providers.news import FinnhubNewsProvider
from app.providers.yahoo import YahooFinanceProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduled cron job — runs inside the web process
# ---------------------------------------------------------------------------

_scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    from cron import main as run_cron

    _scheduler.add_job(
        run_cron,
        CronTrigger(hour=14, minute=0, day_of_week="mon-fri", timezone="UTC"),
        id="daily_snapshot",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — daily snapshot at 14:00 UTC Mon-Fri")
    yield
    _scheduler.shutdown()


app = FastAPI(
    title="Option Screener API",
    version="0.1.0",
    description="AI Short-Put Option Screener for the wheel strategy",
    lifespan=lifespan,
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

# Request coalescing: if a scan is already running, subsequent requests
# wait for that same result instead of firing a duplicate scan.
# This prevents yfinance rate limiting when multiple users hit the endpoint.
_scan_lock = threading.Lock()
_scan_in_progress: threading.Event | None = None
_scan_result: ScanResult | None = None
_scan_error: Exception | None = None


@app.get("/")
def root() -> dict[str, str]:
    """Root route — used by Railway health checks."""
    return {"service": "option-screener-api", "status": "ok"}


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

    Uses request coalescing: if a full scan (no custom symbols) is already
    running, this request waits for that result instead of starting another.
    Custom symbol scans bypass coalescing since they're lightweight.

    Query params:
        symbols: Optional comma-separated list of symbols to scan
                 instead of the full S&P 500. Useful for testing.
        max_trades: Override the default max trades to return.
    """
    symbol_list = symbols.split(",") if symbols else None

    # Custom symbol scans are lightweight — run directly, no coalescing
    if symbol_list is not None:
        return run_scan(
            market_provider=_yahoo,
            options_provider=_yahoo,
            news_provider=_news,
            symbols=symbol_list,
            max_trades=max_trades,
        )

    return _coalesced_scan(max_trades)


def _coalesced_scan(max_trades: int | None = None) -> ScanResult:
    """Run a full scan, or wait for one already in progress."""
    global _scan_in_progress, _scan_result, _scan_error

    with _scan_lock:
        if _scan_in_progress is not None:
            # A scan is already running — wait for it
            event = _scan_in_progress
        else:
            # No scan running — we'll be the one to run it
            event = threading.Event()
            _scan_in_progress = event
            _scan_result = None
            _scan_error = None
            event = None  # signal that we're the runner

    if event is not None:
        # We're a waiter — block until the runner finishes
        event.wait()
        if _scan_error is not None:
            raise _scan_error
        assert _scan_result is not None
        return _scan_result

    # We're the runner — execute the scan
    try:
        result = run_scan(
            market_provider=_yahoo,
            options_provider=_yahoo,
            news_provider=_news,
            symbols=None,
            max_trades=max_trades,
        )
        with _scan_lock:
            _scan_result = result
            _scan_error = None
        return result
    except Exception as exc:
        with _scan_lock:
            _scan_error = exc
        raise
    finally:
        with _scan_lock:
            done_event = _scan_in_progress
            _scan_in_progress = None
        if done_event is not None:
            done_event.set()


@app.get("/api/market-status", response_model=MarketRiskStatus)
def get_market_status() -> MarketRiskStatus:
    """Get current market risk indicators (VIX + SPY trend)."""
    return assess_market_risk(_yahoo)


# ---------------------------------------------------------------------------
# Report endpoints — backtesting data
# ---------------------------------------------------------------------------


@app.get("/api/report/summary", response_model=SummaryResponse)
def get_report_summary() -> SummaryResponse:
    """Return aggregate backtesting statistics."""
    conn = get_connection(settings.db_path)
    try:
        stats = get_summary_stats(conn)
        return SummaryResponse(**stats)
    finally:
        conn.close()


@app.get("/api/report/trades", response_model=TradesResponse)
def get_report_trades(status: str = "all") -> TradesResponse:
    """Return trade list filtered by status with computed fields."""
    conn = get_connection(settings.db_path)
    try:
        rows = get_trades_by_status(conn, status)
        today = date.today()
        trades = []
        for row in rows:
            days_remaining = None
            if row.get("outcome") is None:
                expiry = date.fromisoformat(row["expiry"])
                days_remaining = max((expiry - today).days, 0)
            trades.append(TradeItem(**row, days_remaining=days_remaining))
        return TradesResponse(trades=trades)
    finally:
        conn.close()
