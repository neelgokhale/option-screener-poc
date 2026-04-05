"""Tests for the S3 backup module."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.backup import backup_db_to_s3, run_backup

FAKE_TODAY = date(2026, 4, 5)


def _mock_s3(list_contents=None):
    """Create a mock boto3 S3 client."""
    client = MagicMock()
    client.list_objects_v2.return_value = {
        "Contents": list_contents or []
    }
    return client


class TestBackupUpload:
    """Behavior 1: Upload produces correct S3 key."""

    @patch("app.backup._today", return_value=FAKE_TODAY)
    @patch("app.backup.boto3")
    def test_uploads_with_correct_key(self, mock_boto3, _mock_today, tmp_path):
        db_file = tmp_path / "screener.db"
        db_file.write_text("fake-db-content")

        mock_client = _mock_s3()
        mock_boto3.client.return_value = mock_client

        key = backup_db_to_s3(
            db_path=str(db_file),
            bucket="test-bucket",
            region="us-east-1",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )

        assert key == "backups/screener-2026-04-05.db"
        mock_boto3.client.assert_called_once_with(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
        )
        mock_client.upload_file.assert_called_once_with(
            str(db_file), "test-bucket", "backups/screener-2026-04-05.db"
        )


class TestBackupPrune:
    """Behavior 2: Prune deletes old backups after upload."""

    @patch("app.backup._today", return_value=FAKE_TODAY)
    @patch("app.backup.boto3")
    def test_prunes_backups_older_than_retention(self, mock_boto3, _mock_today, tmp_path):
        db_file = tmp_path / "screener.db"
        db_file.write_text("fake-db-content")

        mock_client = _mock_s3(list_contents=[
            {"Key": "backups/screener-2026-02-01.db"},  # 63 days old — delete
            {"Key": "backups/screener-2026-03-01.db"},  # 35 days old — delete
            {"Key": "backups/screener-2026-03-10.db"},  # 26 days old — keep
            {"Key": "backups/screener-2026-04-05.db"},  # today — keep
        ])
        mock_boto3.client.return_value = mock_client

        backup_db_to_s3(
            db_path=str(db_file),
            bucket="test-bucket",
            region="us-east-1",
            retention_days=30,
        )

        mock_client.delete_objects.assert_called_once_with(
            Bucket="test-bucket",
            Delete={
                "Objects": [
                    {"Key": "backups/screener-2026-02-01.db"},
                    {"Key": "backups/screener-2026-03-01.db"},
                ]
            },
        )

    @patch("app.backup._today", return_value=FAKE_TODAY)
    @patch("app.backup.boto3")
    def test_prune_noop_when_all_recent(self, mock_boto3, _mock_today, tmp_path):
        db_file = tmp_path / "screener.db"
        db_file.write_text("fake-db-content")

        mock_client = _mock_s3(list_contents=[
            {"Key": "backups/screener-2026-03-10.db"},  # 26 days old — keep
            {"Key": "backups/screener-2026-04-05.db"},  # today — keep
        ])
        mock_boto3.client.return_value = mock_client

        backup_db_to_s3(
            db_path=str(db_file),
            bucket="test-bucket",
            region="us-east-1",
            retention_days=30,
        )

        mock_client.delete_objects.assert_not_called()


class TestRunBackup:
    """Behaviors 4-5: Graceful failure handling and skip when unconfigured."""

    @patch("app.backup.backup_db_to_s3", side_effect=Exception("S3 unreachable"))
    def test_logs_error_and_does_not_raise(self, _mock_backup, caplog):
        s = SimpleNamespace(
            db_path="data/screener.db",
            s3_bucket_name="test-bucket",
            aws_access_key_id="AKID",
            aws_secret_access_key="SECRET",
            aws_region="us-east-1",
            backup_retention_days=30,
        )

        run_backup(s)  # should not raise

        assert "S3 unreachable" in caplog.text

    @patch("app.backup.backup_db_to_s3")
    def test_skips_when_bucket_not_configured(self, mock_backup, caplog):
        import logging

        s = SimpleNamespace(
            db_path="data/screener.db",
            s3_bucket_name="",
            aws_region="us-east-1",
            backup_retention_days=30,
        )

        with caplog.at_level(logging.INFO, logger="app.backup"):
            run_backup(s)

        mock_backup.assert_not_called()
        assert "skipped" in caplog.text.lower()


class TestCronIntegration:
    """Behavior 6: cron.py calls run_backup as the final step."""

    @patch("cron.run_backup")
    @patch("cron.snapshot_daily_trades", return_value=1)
    @patch("cron.resolve_expired_trades", return_value=0)
    @patch("cron.get_connection")
    @patch("cron.YahooFinanceProvider")
    def test_cron_calls_run_backup(
        self, _provider, mock_conn, _resolve, _snapshot, mock_run_backup
    ):
        from cron import main

        main()

        mock_run_backup.assert_called_once()
