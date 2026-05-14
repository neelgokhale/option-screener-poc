"""Tests for the report API endpoints."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, insert_snapshot, insert_trades, update_trade_outcome


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


class TestReportSummary:
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
