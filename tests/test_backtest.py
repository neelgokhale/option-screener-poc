"""Tests for the backtest harness."""

import json
from datetime import date, datetime, timezone

import pytest

from app.db import get_connection, insert_snapshot, insert_trades, get_unresolved_trades, update_trade_outcome
from app.models.market import MarketRiskStatus
from app.models.option import ScanResult, TradeOutput


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    yield c
    c.close()


class TestCreateBacktestRun:
    def test_creates_run_with_correct_fields(self, conn):
        from app.backtest import create_backtest_run

        params = {
            "min_dte": 14,
            "max_dte": 21,
            "min_pop": 0.70,
            "min_premium_yield": 0.005,
        }
        run_id = create_backtest_run(
            conn,
            name="smoke-test",
            date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15),
            scan_frequency="weekly",
            strategy_params=params,
        )

        assert isinstance(run_id, int)

        row = conn.execute(
            "SELECT * FROM backtest_runs WHERE id = ?", (run_id,)
        ).fetchone()

        assert row["name"] == "smoke-test"
        assert row["date_range_start"] == "2025-05-01"
        assert row["date_range_end"] == "2025-05-15"
        assert row["scan_frequency"] == "weekly"
        assert json.loads(row["strategy_params"]) == params
        assert row["started_at"] is not None
        assert row["completed_at"] is None


SAMPLE_SNAPSHOT = {
    "snapshot_date": "2025-05-05",
    "universe_size": 500,
    "qualified_stocks": 42,
    "trades_screened": 128,
    "market_risk_elevated": False,
    "vix_level": 18.5,
    "spy_price": 520.0,
}


class TestInsertSnapshotBacktestTag:
    def test_snapshot_tagged_with_backtest_run_id(self, conn):
        from app.backtest import create_backtest_run

        run_id = create_backtest_run(
            conn,
            name="tag-test",
            date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15),
            scan_frequency="weekly",
            strategy_params={},
        )

        snapshot_id = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "backtest_run_id": run_id})

        row = conn.execute(
            "SELECT backtest_run_id FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        assert row["backtest_run_id"] == run_id

    def test_snapshot_without_backtest_run_id_is_null(self, conn):
        snapshot_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)

        row = conn.execute(
            "SELECT backtest_run_id FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        assert row["backtest_run_id"] is None


class TestSnapshotExistsForRun:
    def test_returns_true_for_existing_snapshot(self, conn):
        from app.backtest import create_backtest_run, snapshot_exists_for_run

        run_id = create_backtest_run(
            conn,
            name="resume-test",
            date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15),
            scan_frequency="weekly",
            strategy_params={},
        )
        insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "backtest_run_id": run_id})

        assert snapshot_exists_for_run(conn, run_id, date(2025, 5, 5)) is True

    def test_returns_false_for_missing_date(self, conn):
        from app.backtest import create_backtest_run, snapshot_exists_for_run

        run_id = create_backtest_run(
            conn,
            name="resume-test-2",
            date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15),
            scan_frequency="weekly",
            strategy_params={},
        )

        assert snapshot_exists_for_run(conn, run_id, date(2025, 5, 5)) is False

    def test_ignores_snapshots_from_other_runs(self, conn):
        from app.backtest import create_backtest_run, snapshot_exists_for_run

        run_a = create_backtest_run(
            conn, name="run-a", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )
        run_b = create_backtest_run(
            conn, name="run-b", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )
        insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "backtest_run_id": run_a})

        assert snapshot_exists_for_run(conn, run_b, date(2025, 5, 5)) is False


SAMPLE_TRADE = {
    "rank": 1,
    "symbol": "AAPL",
    "expiry": "2025-05-09",
    "strike": 200.0,
    "premium": 2.50,
    "pop": 0.82,
    "delta": -0.18,
    "theta": -0.05,
    "implied_volatility": 0.25,
    "expected_value": 1.80,
    "days_to_expiry": 14,
    "support_level": 195.0,
    "current_price": 215.0,
    "premium_yield": 0.65,
    "open_interest": 5000,
    "safety_score": 0.75,
    "adjusted_score": 3.15,
    "next_earnings": "2025-06-01",
}


class TestCollectStrategyParams:
    def test_captures_all_engine_thresholds(self):
        from app.backtest import collect_strategy_params

        params = collect_strategy_params()

        assert params["universe"]["min_market_cap"] == 10_000_000_000
        assert params["universe"]["min_roe"] == 0.10
        assert params["universe"]["max_debt_to_ebitda"] == 4.0
        assert params["universe"]["min_avg_volume"] == 2_000_000

        assert params["options"]["min_dte"] == 14
        assert params["options"]["max_dte"] == 21
        assert params["options"]["min_delta"] == -0.35
        assert params["options"]["max_delta"] == -0.10
        assert params["options"]["min_pop"] == 0.70
        assert params["options"]["min_premium_yield"] == 0.005
        assert params["options"]["min_open_interest"] == 1000

        assert params["risk_filter"]["sentiment_threshold"] == -0.35
        assert params["risk_filter"]["relevance_threshold"] == 0.5

        assert params["safety_weights"]["distance"] == 0.25
        assert params["safety_weights"]["correlation"] == 0.10
        assert params["safety_weights"]["iv_rank"] == 0.15
        assert params["safety_weights"]["flow"] == 0.25
        assert params["safety_weights"]["market"] == 0.15
        assert params["safety_weights"]["sentiment"] == 0.10

        assert params["market_risk"]["vix_threshold"] == 25.0


class TestGetUnresolvedTradesScoped:
    def test_returns_only_trades_from_specified_run(self, conn):
        from app.backtest import create_backtest_run

        run_a = create_backtest_run(
            conn, name="run-a", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )
        run_b = create_backtest_run(
            conn, name="run-b", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )

        snap_a = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "backtest_run_id": run_a})
        insert_trades(conn, snap_a, [SAMPLE_TRADE])

        snap_b = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-05",
            "backtest_run_id": run_b,
        })
        insert_trades(conn, snap_b, [{**SAMPLE_TRADE, "symbol": "MSFT"}])

        trades = get_unresolved_trades(conn, date(2025, 5, 10), backtest_run_id=run_a)
        assert len(trades) == 1
        assert trades[0]["symbol"] == "AAPL"

    def test_does_not_return_live_trades(self, conn):
        from app.backtest import create_backtest_run

        run_id = create_backtest_run(
            conn, name="scoped-test", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )

        live_snap = insert_snapshot(conn, SAMPLE_SNAPSHOT)
        insert_trades(conn, live_snap, [SAMPLE_TRADE])

        trades = get_unresolved_trades(conn, date(2025, 5, 10), backtest_run_id=run_id)
        assert len(trades) == 0


def _make_trade(symbol: str, expiry: date, strike: float = 200.0) -> TradeOutput:
    return TradeOutput(
        rank=1,
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        premium=2.50,
        pop=0.82,
        delta=-0.18,
        theta=-0.05,
        implied_volatility=0.25,
        expected_value=1.80,
        days_to_expiry=14,
        support_level=195.0,
        current_price=215.0,
        premium_yield=0.65,
        open_interest=5000,
        safety_score=0.75,
        adjusted_score=3.15,
    )


def _make_scan_result(trades: list[TradeOutput]) -> ScanResult:
    return ScanResult(
        trades=trades,
        universe_size=500,
        qualified_stocks=42,
        trades_screened=128,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
    )


FIXED_MARKET_RISK = MarketRiskStatus(
    vix_level=18.5,
    spy_price=520.0,
    spy_sma_20=515.0,
    spy_above_sma=True,
    risk_elevated=False,
)


class TestBacktestRunnerProducesSnapshots:
    def test_two_week_window_creates_two_snapshots(self, conn):
        from app.backtest import BacktestRunner

        scan_dates_called = []

        def fake_scan(as_of: date) -> ScanResult:
            scan_dates_called.append(as_of)
            return _make_scan_result([_make_trade("AAPL", date(2025, 5, 16))])

        runner = BacktestRunner(
            conn=conn,
            scan_fn=fake_scan,
            settlement_price_fn=lambda sym, exp: 210.0,
            market_risk_fn=lambda d: FIXED_MARKET_RISK,
        )
        run_id = runner.run(
            start=date(2025, 5, 5),
            end=date(2025, 5, 16),
            frequency="weekly",
            name="snapshot-test",
        )

        assert scan_dates_called == [date(2025, 5, 5), date(2025, 5, 12)]

        snapshots = conn.execute(
            "SELECT * FROM snapshots WHERE backtest_run_id = ? ORDER BY snapshot_date",
            (run_id,),
        ).fetchall()
        assert len(snapshots) == 2
        assert snapshots[0]["snapshot_date"] == "2025-05-05"
        assert snapshots[1]["snapshot_date"] == "2025-05-12"

        trades = conn.execute(
            "SELECT COUNT(*) as cnt FROM snapshot_trades t JOIN snapshots s ON t.snapshot_id = s.id WHERE s.backtest_run_id = ?",
            (run_id,),
        ).fetchone()
        assert trades["cnt"] == 2

        run_row = conn.execute(
            "SELECT * FROM backtest_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert run_row["completed_at"] is not None


class TestBacktestRunnerInlineResolution:
    def test_resolves_expired_trades_after_each_scan(self, conn):
        from app.backtest import BacktestRunner

        def fake_scan(as_of: date) -> ScanResult:
            if as_of == date(2025, 5, 5):
                return _make_scan_result([
                    _make_trade("AAPL", expiry=date(2025, 5, 9), strike=200.0),
                ])
            return _make_scan_result([
                _make_trade("MSFT", expiry=date(2025, 5, 23), strike=300.0),
            ])

        settlement_prices = {"AAPL": 210.0}

        runner = BacktestRunner(
            conn=conn,
            scan_fn=fake_scan,
            settlement_price_fn=lambda sym, exp: settlement_prices.get(sym),
            market_risk_fn=lambda d: FIXED_MARKET_RISK,
        )
        run_id = runner.run(
            start=date(2025, 5, 5),
            end=date(2025, 5, 16),
            frequency="weekly",
            name="resolution-test",
        )

        aapl_trade = conn.execute(
            """SELECT t.* FROM snapshot_trades t
               JOIN snapshots s ON t.snapshot_id = s.id
               WHERE s.backtest_run_id = ? AND t.symbol = 'AAPL'""",
            (run_id,),
        ).fetchone()
        assert aapl_trade["outcome"] == "OTM"
        assert aapl_trade["settlement_price"] == 210.0
        assert aapl_trade["pnl_pct"] is not None

        msft_trade = conn.execute(
            """SELECT t.* FROM snapshot_trades t
               JOIN snapshots s ON t.snapshot_id = s.id
               WHERE s.backtest_run_id = ? AND t.symbol = 'MSFT'""",
            (run_id,),
        ).fetchone()
        assert msft_trade["outcome"] is None

    def test_does_not_resolve_live_trades(self, conn):
        from app.backtest import BacktestRunner

        live_snap = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-01",
        })
        insert_trades(conn, live_snap, [{
            **SAMPLE_TRADE, "symbol": "LIVE", "expiry": "2025-05-09",
        }])

        runner = BacktestRunner(
            conn=conn,
            scan_fn=lambda d: _make_scan_result([]),
            settlement_price_fn=lambda sym, exp: 210.0,
            market_risk_fn=lambda d: FIXED_MARKET_RISK,
        )
        runner.run(
            start=date(2025, 5, 5),
            end=date(2025, 5, 16),
            frequency="weekly",
            name="no-live-resolve",
        )

        live_trade = conn.execute(
            "SELECT outcome FROM snapshot_trades WHERE symbol = 'LIVE'"
        ).fetchone()
        assert live_trade["outcome"] is None


class TestBacktestRunnerResumability:
    def test_resumes_from_last_completed_date(self, conn):
        from app.backtest import BacktestRunner

        call_count = 0

        def counting_scan(as_of: date) -> ScanResult:
            nonlocal call_count
            call_count += 1
            return _make_scan_result([_make_trade("AAPL", date(2025, 5, 30))])

        runner = BacktestRunner(
            conn=conn,
            scan_fn=counting_scan,
            settlement_price_fn=lambda sym, exp: 210.0,
            market_risk_fn=lambda d: FIXED_MARKET_RISK,
        )

        run_id_1 = runner.run(
            start=date(2025, 5, 5),
            end=date(2025, 5, 16),
            frequency="weekly",
            name="resume-run",
        )
        assert call_count == 2

        call_count = 0
        run_id_2 = runner.run(
            start=date(2025, 5, 5),
            end=date(2025, 5, 16),
            frequency="weekly",
            name="resume-run",
        )

        assert run_id_2 == run_id_1
        assert call_count == 0

        snapshots = conn.execute(
            "SELECT COUNT(*) as cnt FROM snapshots WHERE backtest_run_id = ?",
            (run_id_1,),
        ).fetchone()
        assert snapshots["cnt"] == 2


class TestGetBacktestSummary:
    def test_computes_correct_stats(self, conn):
        from app.backtest import create_backtest_run, get_backtest_summary

        run_id = create_backtest_run(
            conn, name="summary-test", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )

        snap1 = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-05", "backtest_run_id": run_id,
        })
        insert_trades(conn, snap1, [
            {**SAMPLE_TRADE, "symbol": "AAPL"},
            {**SAMPLE_TRADE, "symbol": "MSFT"},
        ])
        t1, t2 = [r["id"] for r in conn.execute(
            "SELECT id FROM snapshot_trades WHERE snapshot_id = ? ORDER BY id", (snap1,)
        ).fetchall()]
        update_trade_outcome(conn, t1, "OTM", 210.0, 1.25)
        update_trade_outcome(conn, t2, "ITM", 195.0, -1.25)

        snap2 = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-12", "backtest_run_id": run_id,
        })
        insert_trades(conn, snap2, [{**SAMPLE_TRADE, "symbol": "GOOGL"}])
        t3 = conn.execute(
            "SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap2,)
        ).fetchone()["id"]
        update_trade_outcome(conn, t3, "OTM", 220.0, 1.25)

        summary = get_backtest_summary(conn, run_id)

        assert summary["total_scans"] == 2
        assert summary["total_trades"] == 3
        assert summary["total_resolved"] == 3
        assert summary["win_rate"] == pytest.approx(66.67, rel=0.01)
        assert summary["avg_pnl_pct"] == pytest.approx(0.4167, rel=0.01)
        assert summary["best_trade"]["symbol"] in ("AAPL", "GOOGL")
        assert summary["best_trade"]["pnl_pct"] == 1.25
        assert summary["worst_trade"]["symbol"] == "MSFT"
        assert summary["worst_trade"]["pnl_pct"] == -1.25

    def test_ignores_trades_from_other_runs(self, conn):
        from app.backtest import create_backtest_run, get_backtest_summary

        run_a = create_backtest_run(
            conn, name="summary-a", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )
        run_b = create_backtest_run(
            conn, name="summary-b", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )

        snap_a = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "backtest_run_id": run_a,
        })
        insert_trades(conn, snap_a, [SAMPLE_TRADE])
        ta = conn.execute("SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap_a,)).fetchone()["id"]
        update_trade_outcome(conn, ta, "OTM", 210.0, 1.25)

        snap_b = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-12", "backtest_run_id": run_b,
        })
        insert_trades(conn, snap_b, [SAMPLE_TRADE])
        tb = conn.execute("SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap_b,)).fetchone()["id"]
        update_trade_outcome(conn, tb, "ITM", 195.0, -5.0)

        summary = get_backtest_summary(conn, run_a)
        assert summary["total_trades"] == 1
        assert summary["win_rate"] == pytest.approx(100.0)


class TestGetEquityCurve:
    def test_returns_cumulative_pnl_series(self, conn):
        from app.backtest import create_backtest_run, get_equity_curve

        run_id = create_backtest_run(
            conn, name="curve-test", date_range_start=date(2025, 5, 1),
            date_range_end=date(2025, 5, 15), scan_frequency="weekly", strategy_params={},
        )

        snap1 = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-05", "backtest_run_id": run_id,
        })
        insert_trades(conn, snap1, [
            {**SAMPLE_TRADE, "symbol": "AAPL"},
            {**SAMPLE_TRADE, "symbol": "MSFT"},
        ])
        ids1 = [r["id"] for r in conn.execute(
            "SELECT id FROM snapshot_trades WHERE snapshot_id = ? ORDER BY id", (snap1,)
        ).fetchall()]
        update_trade_outcome(conn, ids1[0], "OTM", 210.0, 1.25)
        update_trade_outcome(conn, ids1[1], "ITM", 195.0, -1.25)

        snap2 = insert_snapshot(conn, {
            **SAMPLE_SNAPSHOT, "snapshot_date": "2025-05-12", "backtest_run_id": run_id,
        })
        insert_trades(conn, snap2, [{**SAMPLE_TRADE, "symbol": "GOOGL"}])
        id2 = conn.execute(
            "SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap2,)
        ).fetchone()["id"]
        update_trade_outcome(conn, id2, "OTM", 220.0, 1.25)

        curve = get_equity_curve(conn, run_id)

        assert len(curve) == 2
        assert curve[0]["date"] == "2025-05-05"
        assert curve[0]["cumulative_pnl"] == pytest.approx(0.0)
        assert curve[1]["date"] == "2025-05-12"
        assert curve[1]["cumulative_pnl"] == pytest.approx(1.25)
