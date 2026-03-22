"""Tests for the options screening engine."""

from datetime import date, timedelta

import pandas as pd

from app.engine.options_screener import screen_options_for_stock, _estimate_delta
from app.models.option import OptionContract, OptionsChain
from app.models.stock import StockProfile
from app.providers.base import MarketDataProvider, OptionsDataProvider
from tests.conftest import make_stock


def _make_put(
    symbol: str = "TEST",
    strike: float = 135.0,
    bid: float = 1.40,
    ask: float = 1.60,
    delta: float = -0.22,
    iv: float = 0.30,
    oi: int = 5000,
    volume: int = 500,
    expiry: date | None = None,
) -> OptionContract:
    """Create a put contract with sensible defaults."""
    if expiry is None:
        expiry = date.today() + timedelta(days=17)
    return OptionContract(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type="put",
        bid=bid,
        ask=ask,
        last_price=(bid + ask) / 2,
        delta=delta,
        theta=-0.05,
        implied_volatility=iv,
        open_interest=oi,
        volume=volume,
    )


class MockOptionsProvider(OptionsDataProvider):
    """Mock provider returning configurable options chains."""

    def __init__(self, chains: dict[str, OptionsChain]) -> None:
        self._chains = chains

    def get_expiry_dates(self, symbol: str) -> list[str]:
        return [
            chain.expiry.isoformat()
            for chain in self._chains.values()
            if chain.symbol == symbol
        ]

    def get_options_chain(self, symbol: str, expiry: str) -> OptionsChain:
        return self._chains[expiry]


class MockMarketProvider(MarketDataProvider):
    """Mock provider with configurable price history."""

    def __init__(self, stock: StockProfile, support_price: float) -> None:
        self._stock = stock
        self._support = support_price

    def get_stock_info(self, symbol: str) -> StockProfile | None:
        return self._stock if symbol == self._stock.symbol else None

    def get_price_history(
        self, symbol: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        # Create a price history with a clear dip at support_price
        prices = (
            [self._stock.current_price - i * 0.5 for i in range(10)]
            + [self._support]  # The dip
            + [self._stock.current_price - i * 0.3 for i in range(9, -1, -1)]
        )
        return pd.DataFrame({
            "Open": prices,
            "High": [p + 1 for p in prices],
            "Low": prices,
            "Close": [p + 0.5 for p in prices],
            "Volume": [1000000] * len(prices),
        })

    def get_sp500_symbols(self) -> list[str]:
        return [self._stock.symbol]


class TestOptionsScreener:
    def _setup(
        self,
        stock: StockProfile | None = None,
        puts: list[OptionContract] | None = None,
        support: float = 138.0,
    ) -> tuple[MockMarketProvider, MockOptionsProvider, StockProfile]:
        if stock is None:
            stock = make_stock(symbol="TEST", current_price=150.0)
        if puts is None:
            expiry = date.today() + timedelta(days=17)
            puts = [_make_put(symbol=stock.symbol, expiry=expiry)]

        expiry_str = puts[0].expiry.isoformat()
        chain = OptionsChain(
            symbol=stock.symbol,
            expiry=puts[0].expiry,
            puts=puts,
            calls=[],
        )
        market = MockMarketProvider(stock, support)
        options = MockOptionsProvider({expiry_str: chain})
        return market, options, stock

    def test_qualifying_put_passes(self) -> None:
        """A well-behaved put should pass all filters."""
        market, options, stock = self._setup()
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 1
        assert trades[0].symbol == "TEST"
        assert trades[0].pop > 0.70

    def test_low_oi_excluded(self) -> None:
        """Puts with OI < 1000 should be filtered out."""
        expiry = date.today() + timedelta(days=17)
        put = _make_put(oi=500, expiry=expiry)
        market, options, stock = self._setup(puts=[put])
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 0

    def test_delta_too_aggressive_excluded(self) -> None:
        """Delta more negative than -0.30 is too risky."""
        expiry = date.today() + timedelta(days=17)
        put = _make_put(delta=-0.35, expiry=expiry)
        market, options, stock = self._setup(puts=[put])
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 0

    def test_delta_too_conservative_excluded(self) -> None:
        """Delta less negative than -0.15 has too little premium."""
        expiry = date.today() + timedelta(days=17)
        put = _make_put(delta=-0.10, expiry=expiry)
        market, options, stock = self._setup(puts=[put])
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 0

    def test_strike_above_support_excluded(self) -> None:
        """Strike at or above support is too risky."""
        expiry = date.today() + timedelta(days=17)
        put = _make_put(strike=145.0, expiry=expiry)  # Above support of 138
        market, options, stock = self._setup(puts=[put], support=138.0)
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 0

    def test_ev_fields_populated(self) -> None:
        """Verify EV-related fields are computed and positive."""
        market, options, stock = self._setup()
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 1
        trade = trades[0]
        assert trade.expected_value > 0
        assert trade.premium_yield > 0
        assert trade.mid_price > 0

    def test_no_qualifying_expiries(self) -> None:
        """If no expiries are in the 14-21 day window, return empty."""
        expiry = date.today() + timedelta(days=45)  # Too far out
        put = _make_put(expiry=expiry)
        market, options, stock = self._setup(puts=[put])
        trades = screen_options_for_stock(stock, market, options)
        assert len(trades) == 0


class TestEstimateDelta:
    def test_atm_put_delta_near_negative_half(self) -> None:
        """ATM put delta should be around -0.50."""
        delta = _estimate_delta(spot=150.0, strike=150.0, iv=0.30, dte=20)
        assert -0.55 < delta < -0.45

    def test_otm_put_delta_small(self) -> None:
        """Deep OTM put should have delta close to 0."""
        delta = _estimate_delta(spot=150.0, strike=120.0, iv=0.30, dte=20)
        assert -0.10 < delta < 0.0

    def test_itm_put_delta_near_negative_one(self) -> None:
        """Deep ITM put should have delta close to -1."""
        delta = _estimate_delta(spot=150.0, strike=180.0, iv=0.30, dte=20)
        assert -1.0 < delta < -0.90

    def test_zero_iv_returns_zero(self) -> None:
        assert _estimate_delta(150.0, 140.0, 0.0, 20) == 0.0

    def test_zero_dte_returns_zero(self) -> None:
        assert _estimate_delta(150.0, 140.0, 0.30, 0) == 0.0
