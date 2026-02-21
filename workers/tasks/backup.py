"""
Daily PostgreSQL backup task.
Dumps the database, gzips it, uploads to R2 under backups/YYYY/MM/YYYY-MM-DD.sql.gz
Retains the last 30 daily backups in R2 (deletes older ones automatically).
"""

import gzip
import logging
import os
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from celery_app import app

log = logging.getLogger(__name__)

BUCKET = os.environ.get("R2_BUCKET_NAME", "metricshour-assets")
ENDPOINT = os.environ.get("R2_ENDPOINT", "")
ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "")
SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
KEEP_DAYS = 30


def _r2():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _pg_env() -> dict:
    """Build environment variables for pg_dump from DATABASE_URL."""
    url = urlparse(os.environ["DATABASE_URL"])
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    return env, url


def _dump_and_compress() -> bytes:
    """Run pg_dump and return gzip-compressed bytes."""
    _, url = _pg_env()
    env, _ = _pg_env()

    cmd = [
        "pg_dump",
        "--no-password",
        "--format=plain",
        "--no-owner",
        "--no-acl",
        f"--host={url.hostname}",
        f"--port={url.port or 5432}",
        f"--username={url.username}",
        f"--dbname={url.path.lstrip('/')}",
    ]

    # Aiven requires SSL; pass sslmode via env
    env["PGSSLMODE"] = "require"

    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        timeout=300,  # 5-minute hard limit
    )

    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")

    return gzip.compress(result.stdout, compresslevel=9)


def _prune_old_backups(r2_client) -> None:
    """Delete backups older than KEEP_DAYS from R2."""
    paginator = r2_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix="backups/")

    keys = []
    for page in pages:
        for obj in page.get("Contents", []):
            keys.append((obj["LastModified"], obj["Key"]))

    keys.sort()  # oldest first
    to_delete = keys[:-KEEP_DAYS] if len(keys) > KEEP_DAYS else []

    for _, key in to_delete:
        r2_client.delete_object(Bucket=BUCKET, Key=key)
        log.info("Pruned old backup: %s", key)


@app.task(name="tasks.backup.run_backup", bind=True, max_retries=2, default_retry_delay=300)
def run_backup(self):
    """Dump PostgreSQL → gzip → upload to R2."""
    now = datetime.now(timezone.utc)
    key = f"backups/{now.year}/{now.month:02d}/{now.strftime('%Y-%m-%d')}.sql.gz"

    log.info("Starting backup → %s", key)

    try:
        data = _dump_and_compress()
        size_mb = len(data) / 1_048_576

        r2 = _r2()
        r2.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=data,
            ContentType="application/gzip",
        )
        log.info("Backup uploaded: %s (%.2f MB)", key, size_mb)

        _prune_old_backups(r2)
        log.info("Backup complete")

        return {"key": key, "size_mb": round(size_mb, 2), "timestamp": now.isoformat()}

    except Exception as exc:
        log.error("Backup failed: %s", exc)
        raise self.retry(exc=exc)
