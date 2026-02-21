#!/usr/bin/env python3
"""
MetricsHour — PostgreSQL restore from Cloudflare R2.

Usage:
  python restore.py              # list backups, prompt to pick one
  python restore.py --latest     # restore the most recent backup (still prompts)
  python restore.py --key backups/2026/02/2026-02-21.sql.gz  # restore specific key
  python restore.py --list       # just list available backups and exit

The backup format is: plain SQL dump (pg_dump --format=plain), gzip compressed.
Restore uses: psql (not pg_restore).

Safety:
  - Always shows what it's about to do and asks for explicit confirmation.
  - Stops services before restore, restarts them after.
  - Prints table row counts before and after to verify integrity.
"""

import argparse
import gzip
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../backend/.env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BUCKET = os.environ.get("R2_BUCKET_NAME", "metricshour-assets")
ENDPOINT = os.environ.get("R2_ENDPOINT", "")
ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "")
SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Tables to count rows in for pre/post verification
VERIFY_TABLES = [
    "countries",
    "country_indicators",
    "assets",
    "prices",
    "trade_pairs",
    "stock_country_revenues",
    "users",
]


def _r2():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _pg_conn_args() -> tuple[dict, urlparse]:
    """Return (env dict with PGPASSWORD, parsed URL)."""
    url = urlparse(DATABASE_URL)
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    env["PGSSLMODE"] = "require"
    return env, url


def list_backups() -> list[dict]:
    """Return list of backup objects sorted newest first."""
    r2 = _r2()
    paginator = r2.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix="backups/")
    items = []
    for page in pages:
        for obj in page.get("Contents", []):
            items.append({
                "key": obj["Key"],
                "size_mb": round(obj["Size"] / 1_048_576, 2),
                "last_modified": obj["LastModified"],
            })
    items.sort(key=lambda x: x["last_modified"], reverse=True)
    return items


def print_backups(items: list[dict]) -> None:
    print(f"\n{'#':<4} {'Key':<45} {'Size':>8}  {'Date (UTC)'}")
    print("-" * 75)
    for i, item in enumerate(items):
        ts = item["last_modified"].strftime("%Y-%m-%d %H:%M")
        print(f"{i:<4} {item['key']:<45} {item['size_mb']:>7.2f}MB  {ts}")
    print()


def row_counts() -> dict[str, int]:
    """Query row counts for key tables."""
    env, url = _pg_conn_args()
    counts = {}
    for table in VERIFY_TABLES:
        result = subprocess.run(
            [
                "psql",
                f"--host={url.hostname}",
                f"--port={url.port or 5432}",
                f"--username={url.username}",
                f"--dbname={url.path.lstrip('/')}",
                "--no-password",
                "--tuples-only",
                "--command", f"SELECT COUNT(*) FROM {table};",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            counts[table] = int(result.stdout.strip())
        else:
            counts[table] = -1  # table missing or error
    return counts


def print_counts(label: str, counts: dict[str, int]) -> None:
    print(f"\n  {label}:")
    for table, count in counts.items():
        marker = "  " if count >= 0 else "??"
        val = f"{count:,}" if count >= 0 else "ERROR"
        print(f"    {marker} {table:<35} {val:>10} rows")


def download_backup(key: str) -> bytes:
    """Download a backup from R2 and return decompressed SQL bytes."""
    log.info("Downloading %s from R2...", key)
    r2 = _r2()
    obj = r2.get_object(Bucket=BUCKET, Key=key)
    compressed = obj["Body"].read()
    size_mb = len(compressed) / 1_048_576
    log.info("Downloaded %.2f MB — decompressing...", size_mb)
    sql = gzip.decompress(compressed)
    log.info("Decompressed to %.2f MB SQL", len(sql) / 1_048_576)
    return sql


def stop_services() -> None:
    log.info("Stopping metricshour-api and metricshour-worker...")
    subprocess.run(["systemctl", "stop", "metricshour-api"], check=False)
    subprocess.run(["systemctl", "stop", "metricshour-worker"], check=False)


def start_services() -> None:
    log.info("Starting metricshour-api and metricshour-worker...")
    subprocess.run(["systemctl", "start", "metricshour-api"], check=False)
    subprocess.run(["systemctl", "start", "metricshour-worker"], check=False)


def restore(sql: bytes) -> None:
    """Write SQL to a temp file and pipe to psql."""
    env, url = _pg_conn_args()
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
        f.write(sql)
        tmp_path = f.name

    log.info("Restoring via psql (this may take a few minutes)...")
    try:
        result = subprocess.run(
            [
                "psql",
                f"--host={url.hostname}",
                f"--port={url.port or 5432}",
                f"--username={url.username}",
                f"--dbname={url.path.lstrip('/')}",
                "--no-password",
                "--file", tmp_path,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10-minute limit
        )
        if result.returncode != 0:
            log.error("psql stderr:\n%s", result.stderr[-3000:])
            raise RuntimeError(f"psql restore failed (exit {result.returncode})")
        log.info("psql completed successfully")
    finally:
        os.unlink(tmp_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore MetricsHour DB from R2 backup")
    parser.add_argument("--list", action="store_true", help="List backups and exit")
    parser.add_argument("--latest", action="store_true", help="Select the most recent backup")
    parser.add_argument("--key", help="Restore a specific R2 key")
    args = parser.parse_args()

    # Validate env
    for var in ("DATABASE_URL", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(var):
            sys.exit(f"ERROR: {var} not set. Source your .env file first.")

    backups = list_backups()
    if not backups:
        sys.exit("No backups found in R2 under backups/")

    if args.list:
        print_backups(backups)
        return

    # Select backup
    if args.key:
        selected = next((b for b in backups if b["key"] == args.key), None)
        if not selected:
            sys.exit(f"Key not found in R2: {args.key}")
    elif args.latest:
        selected = backups[0]
    else:
        print_backups(backups)
        try:
            choice = int(input("Enter backup number to restore (Ctrl+C to cancel): ").strip())
            selected = backups[choice]
        except (ValueError, IndexError):
            sys.exit("Invalid selection.")
        except KeyboardInterrupt:
            sys.exit("\nCancelled.")

    # Confirm
    url = urlparse(DATABASE_URL)
    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │              RESTORE CONFIRMATION                   │
  ├─────────────────────────────────────────────────────┤
  │  Backup : {selected['key']:<42}│
  │  Size   : {str(selected['size_mb']) + ' MB':<42}│
  │  Date   : {selected['last_modified'].strftime('%Y-%m-%d %H:%M UTC'):<42}│
  │  Target : {url.hostname:<42}│
  │  DB     : {url.path.lstrip('/'):<42}│
  ├─────────────────────────────────────────────────────┤
  │  This will OVERWRITE the current database.          │
  │  Services will be stopped during restore.           │
  └─────────────────────────────────────────────────────┘""")

    confirm = input("\n  Type YES to proceed: ").strip()
    if confirm != "YES":
        sys.exit("Aborted.")

    # Pre-restore counts
    print("\n  Checking current row counts...")
    before = row_counts()
    print_counts("Before restore", before)

    # Download
    sql = download_backup(selected["key"])

    # Stop services, restore, restart
    stop_services()
    try:
        restore(sql)
    except Exception as exc:
        log.error("Restore failed: %s", exc)
        start_services()
        sys.exit(1)
    finally:
        start_services()

    # Post-restore counts
    print("\n  Verifying restore...")
    after = row_counts()
    print_counts("After restore", after)

    # Summary
    print("\n  Comparison:")
    all_ok = True
    for table in VERIFY_TABLES:
        b, a = before.get(table, 0), after.get(table, 0)
        status = "OK" if a > 0 else "WARN"
        if a <= 0:
            all_ok = False
        diff = f"+{a-b}" if a >= b else str(a - b)
        print(f"    [{status}] {table:<35} {b:>10} → {a:>10}  ({diff})")

    if all_ok:
        print("\n  Restore complete.")
    else:
        print("\n  WARN: Some tables have 0 rows. Investigate before using.")


if __name__ == "__main__":
    main()
