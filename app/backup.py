"""S3 backup module — upload SQLite DB and prune old backups."""

import datetime
import logging

import boto3

logger = logging.getLogger(__name__)

_today = datetime.date.today


def backup_db_to_s3(
    db_path: str,
    bucket: str,
    region: str,
    retention_days: int = 30,
) -> str:
    """Upload SQLite DB to S3 and prune old backups.

    Returns the S3 key of the uploaded file.
    """
    key = f"backups/screener-{_today().isoformat()}.db"
    client = boto3.client("s3", region_name=region)
    client.upload_file(db_path, bucket, key)
    logger.info("Uploaded %s to s3://%s/%s", db_path, bucket, key)

    _prune_old_backups(client, bucket, retention_days)

    return key


def _prune_old_backups(
    client, bucket: str, retention_days: int
) -> None:
    """Delete backups older than retention_days."""
    cutoff = _today() - datetime.timedelta(days=retention_days)
    response = client.list_objects_v2(Bucket=bucket, Prefix="backups/")
    contents = response.get("Contents", [])

    to_delete = [
        obj["Key"]
        for obj in contents
        if (d := _parse_backup_date(obj["Key"])) is not None and d < cutoff
    ]

    if to_delete:
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in to_delete]},
        )
        logger.info("Pruned %d old backup(s)", len(to_delete))


def run_backup(settings) -> None:
    """Run backup with graceful error handling. Logs and swallows exceptions."""
    if not settings.s3_bucket_name:
        logger.info("S3 backup skipped — no bucket configured")
        return

    try:
        backup_db_to_s3(
            db_path=settings.db_path,
            bucket=settings.s3_bucket_name,
            region=settings.aws_region,
            retention_days=settings.backup_retention_days,
        )
    except Exception:
        logger.exception("S3 backup failed")


def _parse_backup_date(key: str) -> datetime.date | None:
    """Extract date from a backup key like backups/screener-2026-04-05.db."""
    try:
        filename = key.split("/")[-1]
        date_str = filename.removeprefix("screener-").removesuffix(".db")
        return datetime.date.fromisoformat(date_str)
    except (ValueError, IndexError):
        return None
