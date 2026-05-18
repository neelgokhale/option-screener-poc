"""Tests for schema additions: backtest_runs table and backtest_run_id on snapshots."""

import sqlite3

from app.db import _create_schema, insert_snapshot


class TestBacktestRunsSchema:
    def test_backtest_runs_table_exists(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_schema(conn)

        conn.execute("""
            INSERT INTO backtest_runs (name, started_at, date_range_start, date_range_end,
                                       scan_frequency, strategy_params)
            VALUES ('test-run', '2026-05-14T10:00:00', '2025-05-01', '2026-05-01',
                    'weekly', '{"max_trades": 15}')
        """)
        conn.commit()

        row = conn.execute("SELECT * FROM backtest_runs WHERE name = 'test-run'").fetchone()
        assert row is not None
        assert row["name"] == "test-run"
        assert row["strategy_params"] == '{"max_trades": 15}'
        assert row["completed_at"] is None

    def test_snapshots_has_backtest_run_id_column(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_schema(conn)

        snapshot_id = insert_snapshot(conn, {
            "snapshot_date": "2026-05-14",
            "universe_size": 500,
            "qualified_stocks": 42,
            "trades_screened": 100,
            "market_risk_elevated": False,
            "vix_level": 18.0,
            "spy_price": 520.0,
        })

        row = conn.execute(
            "SELECT backtest_run_id FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        assert row["backtest_run_id"] is None

    def test_snapshot_with_backtest_run_id(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _create_schema(conn)

        conn.execute("""
            INSERT INTO backtest_runs (name, started_at, date_range_start, date_range_end,
                                       scan_frequency, strategy_params)
            VALUES ('test-run', '2026-05-14T10:00:00', '2025-05-01', '2026-05-01',
                    'weekly', '{}')
        """)
        conn.commit()
        run_id = conn.execute("SELECT id FROM backtest_runs").fetchone()["id"]

        conn.execute("""
            INSERT INTO snapshots (snapshot_date, universe_size, qualified_stocks,
                                   trades_screened, market_risk_elevated, vix_level,
                                   spy_price, backtest_run_id)
            VALUES ('2026-05-14', 500, 42, 100, 0, 18.0, 520.0, ?)
        """, (run_id,))
        conn.commit()

        row = conn.execute("SELECT backtest_run_id FROM snapshots").fetchone()
        assert row["backtest_run_id"] == run_id
