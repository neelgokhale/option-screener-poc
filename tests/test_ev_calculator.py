"""Tests for the expected value calculator."""

from pytest import approx

from app.engine.ev_calculator import (
    calculate_ev,
    calculate_expected_loss,
    calculate_pop,
    calculate_premium_yield,
)


class TestPOP:
    def test_typical_delta(self) -> None:
        assert calculate_pop(-0.25) == 0.75

    def test_low_delta(self) -> None:
        assert calculate_pop(-0.15) == 0.85

    def test_high_delta(self) -> None:
        assert calculate_pop(-0.30) == 0.70

    def test_positive_delta_works(self) -> None:
        """POP formula uses abs(delta), so sign doesn't matter."""
        assert calculate_pop(0.25) == 0.75


class TestPremiumYield:
    def test_typical_yield(self) -> None:
        # $1.50 premium on $150 strike, 18 DTE
        # (1.50 / 150) * (365 / 18) = 0.01 * 20.28 = 0.2028
        yield_val = calculate_premium_yield(1.50, 150.0, 18)
        assert round(yield_val, 4) == 0.2028

    def test_zero_strike_returns_zero(self) -> None:
        assert calculate_premium_yield(1.50, 0.0, 18) == 0.0

    def test_zero_dte_returns_zero(self) -> None:
        assert calculate_premium_yield(1.50, 150.0, 0) == 0.0


class TestExpectedLoss:
    def test_typical_loss(self) -> None:
        # Strike $150, support $142 → loss = $8 per share
        assert calculate_expected_loss(150.0, 142.0) == 8.0

    def test_support_above_strike_clamped(self) -> None:
        """Shouldn't happen, but guard against it."""
        assert calculate_expected_loss(150.0, 155.0) == 0.0

    def test_support_equals_strike(self) -> None:
        assert calculate_expected_loss(150.0, 150.0) == 0.0


class TestEV:
    def test_positive_ev(self) -> None:
        # POP 75%, mid $1.50, expected loss $5
        # EV = (0.75 * 150) - (0.25 * 500) = 112.50 - 125 = -12.50
        # Actually that's negative. Let's use better numbers.
        # POP 80%, mid $1.50, expected loss $3
        # EV = (0.80 * 150) - (0.20 * 300) = 120 - 60 = +60
        ev = calculate_ev(0.80, 1.50, 3.0)
        assert ev == approx(60.0)

    def test_negative_ev(self) -> None:
        # POP 70%, mid $0.50, expected loss $10
        # EV = (0.70 * 50) - (0.30 * 1000) = 35 - 300 = -265
        ev = calculate_ev(0.70, 0.50, 10.0)
        assert ev == approx(-265.0)

    def test_zero_premium_zero_ev(self) -> None:
        ev = calculate_ev(0.80, 0.0, 5.0)
        assert ev == approx(-100.0)  # (0.80 * 0) - (0.20 * 500)

    def test_breakeven_ev(self) -> None:
        # Find the breakeven: POP * mid * 100 = (1-POP) * loss * 100
        # 0.75 * mid * 100 = 0.25 * 4 * 100 → mid = 1.333...
        ev = calculate_ev(0.75, 4.0 / 3.0, 4.0)
        assert abs(ev) < 0.01  # ~0
