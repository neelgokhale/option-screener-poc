"""Screening pipeline orchestrator.

Runs the full scan workflow:
1. Universe filter — narrow S&P 500 to qualifying stocks
2. Risk filters — exclude stocks with negative news, pre-market moves, earnings
3. Options screening — find qualifying put contracts for each stock
4. Safety scoring — score each trade on 6 risk factors
5. Market risk check — reduce trade count if VIX/SPY signal stress
6. Rank by adjusted score — EV × (1 + safety), take top N

This module ties all engine components together. Each step is
independently testable, but the pipeline coordinates them into
a single scan operation.
"""

import logging
from datetime import datetime, timezone

from app.config import settings
from app.engine.market_risk import assess_market_risk
from app.engine.options_screener import screen_options_for_stock
from app.engine.risk_filter import apply_risk_filters
from app.engine.safety_score import calculate_adjusted_score, calculate_safety_score
from app.engine.universe import filter_universe
from app.models.option import ScanResult, ScreenedTrade, TradeOutput
from app.providers.base import MarketDataProvider, NewsProvider, OptionsDataProvider

logger = logging.getLogger(__name__)


def run_scan(
    market_provider: MarketDataProvider,
    options_provider: OptionsDataProvider,
    news_provider: NewsProvider | None = None,
    symbols: list[str] | None = None,
    max_trades: int | None = None,
) -> ScanResult:
    """Execute the full screening pipeline.

    Args:
        market_provider: Provider for stock fundamentals and price data.
        options_provider: Provider for options chain data.
        news_provider: Provider for news headlines (optional).
        symbols: Optional override list of symbols (skips universe filter).
        max_trades: Max trades to return (default from settings).

    Returns:
        ScanResult with ranked trades and scan metadata.
    """
    if max_trades is None:
        max_trades = settings.max_trades

    # Step 1: Universe filter
    logger.info("Starting pipeline scan")
    universe_result = filter_universe(market_provider, symbols=symbols)
    qualified_symbols = universe_result.qualified

    logger.info(
        "Universe filter: %d/%d qualified",
        len(qualified_symbols),
        universe_result.total_scanned,
    )

    if not qualified_symbols:
        return _empty_result(universe_result.total_scanned)

    # Step 2: Fetch profiles and apply risk filters
    profiles = {}
    for symbol in qualified_symbols:
        profile = market_provider.get_stock_info(symbol)
        if profile is not None:
            profiles[symbol] = profile

    risk_result = apply_risk_filters(
        symbols=qualified_symbols,
        profiles=profiles,
        market_provider=market_provider,
        news_provider=news_provider,
    )
    filtered_symbols = risk_result.passed

    logger.info(
        "Risk filter: %d/%d passed",
        len(filtered_symbols),
        len(qualified_symbols),
    )

    if not filtered_symbols:
        return _empty_result(
            universe_result.total_scanned,
            qualified_stocks=len(qualified_symbols),
        )

    # Step 3: Assess market risk (VIX + SPY)
    market_risk = assess_market_risk(market_provider)

    if market_risk.risk_elevated:
        max_trades = max(1, max_trades // 2)
        logger.info(
            "Market risk elevated — reducing max trades to %d", max_trades
        )

    # Step 4: Screen options for each filtered stock
    all_trades: list[ScreenedTrade] = []

    for symbol in filtered_symbols:
        stock = profiles.get(symbol)
        if stock is None:
            continue

        trades = screen_options_for_stock(stock, market_provider, options_provider)
        all_trades.extend(trades)

        logger.debug(
            "%s: %d qualifying trades found", symbol, len(trades)
        )

    logger.info("Options screening: %d total trades found", len(all_trades))

    if not all_trades:
        return _empty_result(
            universe_result.total_scanned,
            qualified_stocks=len(qualified_symbols),
        )

    # Step 5: Calculate safety scores and adjusted scores
    scored_trades: list[tuple[ScreenedTrade, float, float]] = []  # (trade, safety, adjusted)

    for trade in all_trades:
        profile = profiles.get(trade.symbol)
        if profile is None:
            continue

        safety = calculate_safety_score(
            trade, profile, market_risk, market_provider, options_provider
        )
        adjusted = calculate_adjusted_score(trade.expected_value, safety.score)
        scored_trades.append((trade, safety.score, adjusted))

    # Step 6: Rank by adjusted score (descending) and take top N
    scored_trades.sort(key=lambda x: x[2], reverse=True)
    top_trades = scored_trades[:max_trades]

    # Convert to output format
    trade_outputs = [
        _to_trade_output(trade, rank=i + 1, safety_score=safety, adjusted_score=adjusted)
        for i, (trade, safety, adjusted) in enumerate(top_trades)
    ]

    return ScanResult(
        trades=trade_outputs,
        universe_size=universe_result.total_scanned,
        qualified_stocks=len(qualified_symbols),
        trades_screened=len(all_trades),
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _to_trade_output(
    trade: ScreenedTrade,
    rank: int,
    safety_score: float,
    adjusted_score: float,
) -> TradeOutput:
    """Convert a ScreenedTrade to a TradeOutput for the API."""
    return TradeOutput(
        rank=rank,
        symbol=trade.symbol,
        expiry=trade.expiry,
        strike=trade.strike,
        premium=round(trade.mid_price, 2),
        pop=round(trade.pop, 4),
        delta=round(trade.delta, 4),
        theta=round(trade.theta, 4) if trade.theta is not None else None,
        implied_volatility=round(trade.implied_volatility, 4),
        expected_value=round(trade.expected_value, 2),
        days_to_expiry=trade.days_to_expiry,
        support_level=round(trade.support_level, 2),
        current_price=round(trade.current_price, 2),
        premium_yield=round(trade.premium_yield, 4),
        open_interest=trade.open_interest,
        safety_score=round(safety_score, 4),
        adjusted_score=round(adjusted_score, 2),
        next_earnings=None,  # TODO: populate from earnings data
    )


def _empty_result(
    universe_size: int,
    qualified_stocks: int = 0,
) -> ScanResult:
    """Return an empty scan result when no trades are found."""
    return ScanResult(
        trades=[],
        universe_size=universe_size,
        qualified_stocks=qualified_stocks,
        trades_screened=0,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
    )
