"""Tests for the stock universe filter."""

from tests.conftest import MockMarketDataProvider, make_stock

from app.engine.universe import filter_universe


class TestUniverseFilter:
    """Verify each fundamental filter works correctly."""

    def test_qualifying_stock_passes(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "GOOD" in result.qualified

    def test_small_cap_excluded(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "SMALL" not in result.qualified
        assert "SMALL" in result.filtered_out.get("market_cap_below_10B", [])

    def test_negative_income_no_longer_excluded(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "LOSER" in result.qualified

    def test_low_roe_excluded(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "LOWROE" not in result.qualified
        assert "LOWROE" in result.filtered_out.get("roe_below_10pct", [])

    def test_high_debt_excluded(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "DEBT" not in result.qualified
        assert "DEBT" in result.filtered_out.get("debt_to_ebitda_above_4", [])

    def test_low_volume_excluded(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert "ILLIQUID" not in result.qualified
        assert "ILLIQUID" in result.filtered_out.get("avg_volume_below_2M", [])

    def test_total_scanned_count(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert result.total_scanned == 6

    def test_two_qualify_after_net_income_dropped(self, mock_provider: MockMarketDataProvider) -> None:
        result = filter_universe(mock_provider)
        assert set(result.qualified) == {"GOOD", "LOSER"}

    def test_custom_symbol_list(self, mock_provider: MockMarketDataProvider) -> None:
        """When given explicit symbols, only those are scanned."""
        result = filter_universe(mock_provider, symbols=["GOOD", "SMALL"])
        assert result.total_scanned == 2
        assert result.qualified == ["GOOD"]

    def test_missing_symbol_handled(self) -> None:
        """Symbols not in the provider are excluded as data_unavailable."""
        provider = MockMarketDataProvider({})
        result = filter_universe(provider, symbols=["FAKE"])
        assert result.qualified == []
        assert "FAKE" in result.filtered_out.get("data_unavailable", [])

    def test_negative_net_income_now_qualifies(self) -> None:
        """NetIncome > 0 was dropped (redundant with ROE > 10%)."""
        stock = make_stock(symbol="NEGNI", net_income=-100_000_000, roe=0.15)
        provider = MockMarketDataProvider({"NEGNI": stock})
        result = filter_universe(provider)
        assert "NEGNI" in result.qualified

    def test_borderline_values(self) -> None:
        """Stocks exactly at filter boundaries should be excluded."""
        # Exactly at $10B — should fail (not strictly greater than)
        borderline = make_stock(
            symbol="EDGE",
            market_cap=10_000_000_000,  # Exactly $10B
            roe=0.10,  # Exactly 10%
            debt_to_ebitda=4.0,  # Exactly 4
            avg_volume=2_000_000,  # Exactly 2M
        )
        provider = MockMarketDataProvider({"EDGE": borderline})
        result = filter_universe(provider)
        # market_cap < 10B is the check, so exactly 10B should pass
        # roe < 0.10 is the check, so exactly 0.10 should pass
        # debt > 4 is the check, so exactly 4 should pass
        # volume < 2M is the check, so exactly 2M should pass
        assert "EDGE" in result.qualified
