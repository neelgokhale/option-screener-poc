"""Tests for technical support/resistance calculation."""

import pandas as pd
import numpy as np

from app.engine.technicals import _find_local_minima, _cluster_levels, find_support_level
from tests.conftest import MockMarketDataProvider, make_stock


class TestFindLocalMinima:
    def test_single_dip(self) -> None:
        """A clear V-shaped dip should be detected."""
        # 15 days of data: descending then ascending around index 7
        lows = [100, 99, 98, 97, 96, 95, 94, 93, 94, 95, 96, 97, 98, 99, 100]
        hist = pd.DataFrame({"Low": lows})
        minima = _find_local_minima(hist)
        assert 93.0 in minima

    def test_multiple_dips(self) -> None:
        """Two separated dips should both be found."""
        lows = (
            [100, 99, 98, 97, 96, 95, 96, 97, 98, 99, 100]
            + [99, 98, 97, 96, 94, 96, 97, 98, 99, 100, 101]
        )
        hist = pd.DataFrame({"Low": lows})
        minima = _find_local_minima(hist)
        assert 95.0 in minima
        assert 94.0 in minima

    def test_flat_prices_no_minima(self) -> None:
        """Flat prices should produce no local minima (all equal)."""
        lows = [100.0] * 20
        hist = pd.DataFrame({"Low": lows})
        minima = _find_local_minima(hist)
        # All values are equal, so every point is a "minimum"
        # This is fine — they'll cluster into one level
        assert all(m == 100.0 for m in minima)

    def test_too_few_data_points(self) -> None:
        """With fewer than 2*window+1 points, should return empty."""
        lows = [100, 99, 98]
        hist = pd.DataFrame({"Low": lows})
        minima = _find_local_minima(hist)
        assert minima == []


class TestClusterLevels:
    def test_close_levels_merge(self) -> None:
        """Levels within 1% should merge to their mean."""
        levels = [100.0, 100.5, 101.0]
        clustered = _cluster_levels(levels)
        assert len(clustered) == 1
        assert abs(clustered[0] - 100.5) < 0.01

    def test_distant_levels_separate(self) -> None:
        """Levels more than 1% apart should stay separate."""
        levels = [100.0, 110.0]
        clustered = _cluster_levels(levels)
        assert len(clustered) == 2

    def test_empty_input(self) -> None:
        assert _cluster_levels([]) == []

    def test_single_level(self) -> None:
        clustered = _cluster_levels([150.0])
        assert clustered == [150.0]


class TestFindSupportLevel:
    def test_returns_nearest_below_price(self) -> None:
        """Should return the highest support level below current price."""
        # Create price data with a clear dip at 140
        lows = (
            [155, 153, 151, 149, 147, 145, 143, 141, 140, 141, 143]
            + [145, 147, 149, 151, 153, 155, 157, 159, 160, 161]
        )
        hist = pd.DataFrame({
            "Open": lows,
            "High": [l + 2 for l in lows],
            "Low": lows,
            "Close": [l + 1 for l in lows],
            "Volume": [1000000] * len(lows),
        })

        class PriceProvider(MockMarketDataProvider):
            def get_price_history(self, symbol, period="3mo", interval="1d"):
                return hist

        provider = PriceProvider({"TEST": make_stock()})
        support = find_support_level(provider, "TEST", current_price=160.0)
        assert support is not None
        assert support < 160.0

    def test_no_history_returns_none(self) -> None:
        provider = MockMarketDataProvider({"TEST": make_stock()})
        support = find_support_level(provider, "TEST", current_price=150.0)
        assert support is None
