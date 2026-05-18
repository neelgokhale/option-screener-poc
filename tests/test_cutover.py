"""Tests for issue #22: production cutover verification."""

import shutil
from datetime import date
from unittest.mock import patch, MagicMock, call

import pytest


class TestBackupRetentionDefault:
    """Behavior 1: backup_retention_days defaults to 90."""

    @patch.dict("os.environ", {}, clear=True)
    def test_default_retention_is_90(self):
        from app.config import Settings

        s = Settings()
        assert s.backup_retention_days == 90


class TestCronEndToEnd:
    """Behavior 2: cron.main() runs resolve → snapshot → backup in order."""

    @patch("cron.run_backup")
    @patch("cron.snapshot_daily_trades", return_value=42)
    @patch("cron.resolve_expired_trades", return_value=3)
    @patch("cron.get_connection")
    @patch("cron.AVClient")
    def test_operations_run_in_order(
        self, mock_client, mock_conn, mock_resolve, mock_snapshot, mock_backup
    ):
        from cron import main

        call_order = []
        mock_resolve.side_effect = lambda *a, **k: call_order.append("resolve") or 3
        mock_snapshot.side_effect = lambda *a, **k: call_order.append("snapshot") or 42
        mock_backup.side_effect = lambda *a, **k: call_order.append("backup")

        main()

        assert call_order == ["resolve", "snapshot", "backup"]

    @patch("cron.run_backup")
    @patch("cron.snapshot_daily_trades", return_value=42)
    @patch("cron.resolve_expired_trades", return_value=3)
    @patch("cron.get_connection")
    @patch("cron.AVClient")
    def test_uses_av_providers(
        self, mock_client_cls, mock_conn, mock_resolve, mock_snapshot, mock_backup
    ):
        from cron import main

        main()

        mock_client_cls.assert_called_once()
        snapshot_call = mock_snapshot.call_args
        market_arg = snapshot_call.args[1]
        options_arg = snapshot_call.args[2]
        assert type(market_arg).__name__ == "AVMarketDataAdapter"
        assert type(options_arg).__name__ == "AVOptionsAdapter"


class TestBackupRoundTrip:
    """Behavior 3: backup + restore round-trip preserves a real SQLite DB."""

    def test_restore_recovers_snapshot_data(self, tmp_path):
        from app.db import get_connection, insert_snapshot

        source_db = str(tmp_path / "source" / "screener.db")
        conn = get_connection(source_db)
        insert_snapshot(conn, {
            "snapshot_date": "2026-05-01",
            "universe_size": 500,
            "qualified_stocks": 40,
            "trades_screened": 120,
            "market_risk_elevated": False,
            "vix_level": 18.0,
            "spy_price": 520.0,
        })
        conn.close()

        staged_path = str(tmp_path / "staged.db")

        def fake_upload(local, bucket, key):
            if key == "backups/screener-latest.db":
                shutil.copy2(local, staged_path)

        def fake_download(bucket, key, local):
            shutil.copy2(staged_path, local)

        mock_client = MagicMock()
        mock_client.upload_file.side_effect = fake_upload
        mock_client.download_file.side_effect = fake_download
        mock_client.list_objects_v2.return_value = {"Contents": []}

        with patch("app.backup.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client

            from app.backup import backup_db_to_s3, restore_db_from_s3

            backup_db_to_s3(
                db_path=source_db,
                bucket="test-bucket",
                region="us-east-1",
            )

            restored_db = str(tmp_path / "restored" / "screener.db")
            (tmp_path / "restored").mkdir()
            restore_db_from_s3(
                db_path=restored_db,
                bucket="test-bucket",
                region="us-east-1",
            )

        restored_conn = get_connection(restored_db)
        row = restored_conn.execute("SELECT * FROM snapshots").fetchone()
        assert row["snapshot_date"] == "2026-05-01"
        assert row["universe_size"] == 500
        assert row["qualified_stocks"] == 40
        assert row["vix_level"] == 18.0
        restored_conn.close()


class TestSnapshotShape:
    """Behavior 4: daily snapshot produces expected shape and row counts."""

    @pytest.fixture
    def conn(self):
        from app.db import get_connection
        c = get_connection(":memory:")
        yield c
        c.close()

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_snapshot_has_all_columns_populated(self, mock_scan, mock_risk, conn):
        from app.models.option import ScanResult, TradeOutput
        from app.models.market import MarketRiskStatus
        from app.orchestrator import snapshot_daily_trades

        mock_scan.return_value = ScanResult(
            trades=[
                TradeOutput(
                    rank=1, symbol="AAPL", expiry=date(2026, 6, 19),
                    strike=200.0, premium=3.10, pop=0.80, delta=-0.20,
                    theta=-0.04, implied_volatility=0.28, expected_value=2.10,
                    days_to_expiry=32, support_level=190.0, current_price=210.0,
                    premium_yield=0.72, open_interest=8000, safety_score=0.78,
                    adjusted_score=3.40, next_earnings=date(2026, 7, 24),
                ),
            ],
            universe_size=500,
            qualified_stocks=45,
            trades_screened=130,
            scan_timestamp="2026-05-18T14:00:00+00:00",
        )
        mock_risk.return_value = MarketRiskStatus(
            vix_level=17.5, vix_threshold=25.0, spy_price=525.0,
            spy_sma_20=518.0, spy_above_sma=True,
            risk_elevated=False, risk_reason=None,
        )

        provider = MagicMock()
        sid = snapshot_daily_trades(conn, provider, provider, today=date(2026, 5, 18))

        snap = conn.execute("SELECT * FROM snapshots WHERE id = ?", (sid,)).fetchone()
        assert snap["snapshot_date"] == "2026-05-18"
        assert snap["universe_size"] == 500
        assert snap["qualified_stocks"] == 45
        assert snap["trades_screened"] == 130
        assert snap["market_risk_elevated"] == 0
        assert snap["vix_level"] == 17.5
        assert snap["spy_price"] == 525.0

        trades = conn.execute(
            "SELECT * FROM snapshot_trades WHERE snapshot_id = ?", (sid,)
        ).fetchall()
        assert len(trades) == 1

        t = trades[0]
        required_fields = [
            "rank", "symbol", "expiry", "strike", "premium", "pop",
            "delta", "theta", "implied_volatility", "expected_value",
            "days_to_expiry", "support_level", "current_price",
            "premium_yield", "open_interest", "safety_score",
            "adjusted_score", "next_earnings",
        ]
        for field in required_fields:
            assert t[field] is not None, f"{field} is None"

    @patch("app.orchestrator.assess_market_risk")
    @patch("app.orchestrator.run_scan")
    def test_snapshot_trade_count_matches_scan(self, mock_scan, mock_risk, conn):
        from app.models.option import ScanResult, TradeOutput
        from app.models.market import MarketRiskStatus
        from app.orchestrator import snapshot_daily_trades

        trades = [
            TradeOutput(
                rank=i, symbol=sym, expiry=date(2026, 6, 19),
                strike=200.0, premium=2.50, pop=0.82, delta=-0.18,
                theta=-0.05, implied_volatility=0.25, expected_value=1.80,
                days_to_expiry=32, support_level=195.0, current_price=215.0,
                premium_yield=0.65, open_interest=5000, safety_score=0.75,
                adjusted_score=3.15, next_earnings=date(2026, 7, 1),
            )
            for i, sym in enumerate(["AAPL", "MSFT", "GOOG"], start=1)
        ]
        mock_scan.return_value = ScanResult(
            trades=trades, universe_size=500, qualified_stocks=42,
            trades_screened=128, scan_timestamp="2026-05-18T14:00:00+00:00",
        )
        mock_risk.return_value = MarketRiskStatus(
            vix_level=18.5, vix_threshold=25.0, spy_price=520.0,
            spy_sma_20=515.0, spy_above_sma=True,
            risk_elevated=False, risk_reason=None,
        )

        provider = MagicMock()
        sid = snapshot_daily_trades(conn, provider, provider, today=date(2026, 5, 18))

        count = conn.execute(
            "SELECT COUNT(*) FROM snapshot_trades WHERE snapshot_id = ?", (sid,)
        ).fetchone()[0]
        assert count == 3
