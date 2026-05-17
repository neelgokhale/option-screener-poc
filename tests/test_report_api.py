"""Tests for the report API endpoints."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import insert_snapshot, insert_trades, update_trade_outcome


SAMPLE_SNAPSHOT = {
    "snapshot_date": "2026-04-01",
    "universe_size": 500,
    "qualified_stocks": 42,
    "trades_screened": 128,
    "market_risk_elevated": False,
    "vix_level": 18.5,
    "spy_price": 520.0,
}

SAMPLE_TRADE = {
    "rank": 1,
    "symbol": "AAPL",
    "expiry": "2026-04-18",
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
    "next_earnings": "2026-05-01",
}


@pytest.fixture
def conn():
    import sqlite3
    from app.db import _create_schema

    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    _create_schema(c)
    yield c
    c.close()


@pytest.fixture
def client(conn):
    with patch("app.server.get_connection", return_value=conn):
        from app.server import app
        yield TestClient(app)


def _seed_mixed_trades(conn):
    """Insert one resolved OTM, one resolved ITM, and one active trade."""
    snap_id = insert_snapshot(conn, SAMPLE_SNAPSHOT)
    snap2_id = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "snapshot_date": "2026-04-04"})

    win = {**SAMPLE_TRADE, "expiry": "2026-04-01"}
    loss = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2026-04-01"}
    active = {**SAMPLE_TRADE, "rank": 3, "symbol": "GOOG", "expiry": "2026-04-25"}
    insert_trades(conn, snap_id, [win, loss])
    insert_trades(conn, snap2_id, [active])

    trades = conn.execute(
        "SELECT id, symbol FROM snapshot_trades WHERE expiry = '2026-04-01'"
    ).fetchall()
    for t in trades:
        if t["symbol"] == "AAPL":
            update_trade_outcome(conn, t["id"], "OTM", 210.0, 1.25)
        else:
            update_trade_outcome(conn, t["id"], "ITM", 195.0, -1.25)


def _seed_backtest_runs(conn):
    """Insert two backtest runs with different started_at times."""
    conn.execute(
        """INSERT INTO backtest_runs (name, started_at, completed_at, date_range_start, date_range_end, scan_frequency, strategy_params)
           VALUES ('run-alpha', '2026-03-01T10:00:00+00:00', '2026-03-01T11:00:00+00:00', '2025-01-01', '2025-06-30', 'weekly', '{}')"""
    )
    conn.execute(
        """INSERT INTO backtest_runs (name, started_at, completed_at, date_range_start, date_range_end, scan_frequency, strategy_params)
           VALUES ('run-beta', '2026-04-15T08:00:00+00:00', '2026-04-15T09:00:00+00:00', '2025-07-01', '2025-12-31', 'weekly', '{}')"""
    )
    conn.commit()


class TestBacktestRuns:
    def test_returns_runs_sorted_by_started_at_desc(self, client, conn):
        _seed_backtest_runs(conn)
        resp = client.get("/api/backtest/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "run-beta"
        assert data[1]["name"] == "run-alpha"
        assert "id" in data[0]
        assert "started_at" in data[0]
        assert "total_trades" in data[0]


    def test_returns_empty_list_when_no_runs(self, client):
        resp = client.get("/api/backtest/runs")
        assert resp.status_code == 200
        assert resp.json() == []


def _seed_run_with_trades(conn) -> int:
    """Create a backtest run with 2 trades (1 resolved OTM, 1 active)."""
    conn.execute(
        """INSERT INTO backtest_runs (id, name, started_at, completed_at, date_range_start, date_range_end, scan_frequency, strategy_params)
           VALUES (99, 'test-run', '2026-03-01T10:00:00+00:00', '2026-03-01T11:00:00+00:00', '2025-01-01', '2025-06-30', 'weekly', '{}')"""
    )
    conn.commit()
    snap_id = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "backtest_run_id": 99})
    resolved = {**SAMPLE_TRADE, "expiry": "2026-04-01"}
    active = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2026-04-25"}
    insert_trades(conn, snap_id, [resolved, active])
    trade_id = conn.execute(
        "SELECT id FROM snapshot_trades WHERE symbol = 'AAPL' AND snapshot_id = ?", (snap_id,)
    ).fetchone()["id"]
    update_trade_outcome(conn, trade_id, "OTM", 210.0, 1.25)
    return 99


def _seed_run_with_equity_data(conn) -> int:
    """Create a run with resolved trades across multiple snapshot dates for equity curve."""
    conn.execute(
        """INSERT INTO backtest_runs (id, name, started_at, completed_at, date_range_start, date_range_end, scan_frequency, strategy_params)
           VALUES (50, 'equity-run', '2026-02-01T10:00:00+00:00', '2026-02-01T11:00:00+00:00', '2025-01-01', '2025-03-31', 'weekly', '{}')"""
    )
    conn.commit()
    # Two snapshots on different dates
    snap1 = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "snapshot_date": "2025-01-15", "backtest_run_id": 50})
    snap2 = insert_snapshot(conn, {**SAMPLE_SNAPSHOT, "snapshot_date": "2025-02-15", "backtest_run_id": 50})
    trade1 = {**SAMPLE_TRADE, "expiry": "2025-01-30"}
    trade2 = {**SAMPLE_TRADE, "rank": 2, "symbol": "MSFT", "expiry": "2025-02-28"}
    insert_trades(conn, snap1, [trade1])
    insert_trades(conn, snap2, [trade2])
    # Resolve both
    t1_id = conn.execute("SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap1,)).fetchone()["id"]
    t2_id = conn.execute("SELECT id FROM snapshot_trades WHERE snapshot_id = ?", (snap2,)).fetchone()["id"]
    update_trade_outcome(conn, t1_id, "OTM", 210.0, 1.5)
    update_trade_outcome(conn, t2_id, "ITM", 195.0, -0.8)
    return 50


class TestEquityCurve:
    def test_returns_cumulative_pnl_for_run(self, client, conn):
        run_id = _seed_run_with_equity_data(conn)
        resp = client.get(f"/api/report/equity-curve?backtest_run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["scan_date"] == "2025-01-15"
        assert data[0]["cumulative_pnl_pct"] == pytest.approx(1.5)
        assert data[0]["trade_count"] == 1
        assert data[1]["scan_date"] == "2025-02-15"
        assert data[1]["cumulative_pnl_pct"] == pytest.approx(0.7)  # 1.5 + (-0.8)
        assert data[1]["trade_count"] == 1


    def test_returns_empty_when_no_resolved_trades(self, client, conn):
        resp = client.get("/api/report/equity-curve?backtest_run_id=999")
        assert resp.status_code == 200
        assert resp.json() == []


class TestReportSummary:
    def test_summary_filters_by_backtest_run_id(self, client, conn):
        _seed_mixed_trades(conn)  # live trades
        run_id = _seed_run_with_trades(conn)  # backtest run trades
        resp = client.get(f"/api/report/summary?backtest_run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tracked"] == 2
        assert data["total_resolved"] == 1
        assert data["total_active"] == 1

    def test_summary_excludes_backtest_data_when_no_run_id(self, client, conn):
        _seed_mixed_trades(conn)  # 3 live trades
        _seed_run_with_trades(conn)  # 2 backtest trades — should NOT appear
        resp = client.get("/api/report/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tracked"] == 3

    def test_summary_with_data(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tracked"] == 3
        assert data["total_resolved"] == 2
        assert data["total_active"] == 1
        assert data["hit_rate"] == 50.0
        assert data["date_range_start"] == "2026-04-01"
        assert data["date_range_end"] == "2026-04-04"

    def test_summary_empty_state(self, client):
        resp = client.get("/api/report/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tracked"] == 0
        assert data["total_resolved"] == 0
        assert data["total_active"] == 0
        assert data["hit_rate"] is None
        assert data["avg_return_pct"] is None
        assert data["date_range_start"] is None


class TestReportTrades:
    def test_trades_filters_by_backtest_run_id(self, client, conn):
        _seed_mixed_trades(conn)  # 3 live trades
        run_id = _seed_run_with_trades(conn)  # 2 backtest trades
        resp = client.get(f"/api/report/trades?backtest_run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trades"]) == 2
        symbols = {t["symbol"] for t in data["trades"]}
        assert symbols == {"AAPL", "MSFT"}

    def test_trades_excludes_backtest_data_when_no_run_id(self, client, conn):
        _seed_mixed_trades(conn)  # 3 live trades
        _seed_run_with_trades(conn)  # 2 backtest trades — should NOT appear
        resp = client.get("/api/report/trades")
        assert resp.status_code == 200
        assert len(resp.json()["trades"]) == 3

    def test_filter_active(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/trades?status=active")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trades"]) == 1
        assert data["trades"][0]["symbol"] == "GOOG"
        assert data["trades"][0]["outcome"] is None

    def test_filter_resolved(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/trades?status=resolved")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trades"]) == 2
        symbols = {t["symbol"] for t in data["trades"]}
        assert symbols == {"AAPL", "MSFT"}

    def test_filter_all(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/trades?status=all")
        assert resp.status_code == 200
        assert len(resp.json()["trades"]) == 3

    def test_active_trade_has_days_remaining(self, client, conn):
        _seed_mixed_trades(conn)
        mock_date = type("FakeDate", (), {
            "today": staticmethod(lambda: date(2026, 4, 10)),
            "fromisoformat": staticmethod(date.fromisoformat),
        })
        with patch("app.server.date", mock_date):
            resp = client.get("/api/report/trades?status=active")
        trade = resp.json()["trades"][0]
        # GOOG expiry is 2026-04-25, today is 2026-04-10 → 15 days remaining
        assert trade["days_remaining"] == 15

    def test_resolved_trade_has_no_days_remaining(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/trades?status=resolved")
        for trade in resp.json()["trades"]:
            assert trade["days_remaining"] is None

    def test_empty_state(self, client):
        resp = client.get("/api/report/trades")
        assert resp.status_code == 200
        assert resp.json()["trades"] == []

    def test_defaults_to_all(self, client, conn):
        _seed_mixed_trades(conn)
        resp = client.get("/api/report/trades")
        assert resp.status_code == 200
        assert len(resp.json()["trades"]) == 3
