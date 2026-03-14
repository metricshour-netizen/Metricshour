"""
Celery failure alerting + dead-letter queue.

Wired via the task_failure signal in celery_app.py — no changes needed in
individual task files. Fires only on FINAL failures (after all retries exhausted).

Delivery:
  1. Structured log to /var/log/metricshour/celery-failures.log (always)
  2. Telegram message (if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set in .env)
  3. Discord webhook embed (if DISCORD_WEBHOOK_URL is set in .env)
  4. Redis dead-letter queue — last 100 failures stored at worker:dlq (always)
"""

import json
import logging
import os
import socket
import traceback
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

FAILURE_LOG = "/var/log/metricshour/celery-failures.log"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
_TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DLQ_KEY = "worker:dlq"
DLQ_MAX = 100  # keep last 100 failures


def _log_failure(task_name: str, exc: BaseException, tb: str, retries: int) -> None:
    """Append a structured entry to the failure log file."""
    now = datetime.now(timezone.utc).isoformat()
    host = socket.gethostname()
    try:
        with open(FAILURE_LOG, "a") as f:
            f.write(
                f"[{now}] TASK_FAILURE host={host} task={task_name} "
                f"retries={retries} exc={type(exc).__name__}: {exc}\n"
                f"{tb}\n"
                + "-" * 80 + "\n"
            )
    except OSError as e:
        log.error("Could not write to failure log %s: %s", FAILURE_LOG, e)


def _send_telegram(task_name: str, exc: BaseException, tb: str, retries: int) -> None:
    """Send a Telegram alert to the admin chat."""
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        return
    host = socket.gethostname()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tb_lines = tb.strip().splitlines()
    tb_short = "\n".join(tb_lines[-6:])
    if len(tb_short) > 600:
        tb_short = "..." + tb_short[-600:]

    text = (
        f"🔴 <b>Worker Task Failed</b>\n\n"
        f"<b>Task:</b> <code>{task_name}</code>\n"
        f"<b>Error:</b> <code>{type(exc).__name__}: {str(exc)[:200]}</code>\n"
        f"<b>Retries:</b> {retries}\n"
        f"<b>Host:</b> {host}\n"
        f"<b>Time:</b> {now}\n\n"
        f"<pre>{tb_short}</pre>"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        ).raise_for_status()
        log.info("Telegram alert sent for %s", task_name)
    except Exception as e:
        log.error("Failed to send Telegram alert: %s", e)


def _send_discord(task_name: str, exc: BaseException, tb: str, retries: int) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    host = socket.gethostname()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tb_lines = tb.strip().splitlines()
    tb_short = "\n".join(tb_lines[-10:])
    if len(tb_short) > 900:
        tb_short = "..." + tb_short[-900:]
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [{
            "title": "Celery Task Failed",
            "color": 0xE53935,
            "fields": [
                {"name": "Task", "value": f"`{task_name}`", "inline": True},
                {"name": "Retries", "value": str(retries), "inline": True},
                {"name": "Host", "value": host, "inline": True},
                {"name": "Exception", "value": f"`{type(exc).__name__}: {str(exc)[:200]}`", "inline": False},
                {"name": "Traceback", "value": f"```\n{tb_short}\n```", "inline": False},
            ],
            "footer": {"text": f"metricshour · {now}"},
        }]}, timeout=10).raise_for_status()
        log.info("Discord alert sent for %s", task_name)
    except Exception as e:
        log.error("Failed to send Discord alert: %s", e)


def _store_dlq(task_name: str, exc: BaseException, tb: str, retries: int) -> None:
    """Push failure to Redis dead-letter queue, capped at DLQ_MAX entries."""
    try:
        from app.storage import get_redis
        r = get_redis()
        entry = json.dumps({
            "task": task_name,
            "exc_type": type(exc).__name__,
            "exc_msg": str(exc)[:500],
            "retries": retries,
            "host": socket.gethostname(),
            "ts": datetime.now(timezone.utc).isoformat(),
            "tb": "\n".join(tb.strip().splitlines()[-10:]),
        })
        r.lpush(DLQ_KEY, entry)
        r.ltrim(DLQ_KEY, 0, DLQ_MAX - 1)
    except Exception as e:
        log.debug("DLQ write failed: %s", e)


def on_task_failure(task_name: str, exc: BaseException, retries: int = 0) -> None:
    """
    Called from the task_failure Celery signal handler in celery_app.py.
    Fires only on FINAL failure (after all retries exhausted).
    """
    tb = traceback.format_exc()
    _log_failure(task_name, exc, tb, retries)
    _send_telegram(task_name, exc, tb, retries)
    _send_discord(task_name, exc, tb, retries)
    _store_dlq(task_name, exc, tb, retries)
    log.error("FINAL FAILURE: %s after %d retries — %s: %s", task_name, retries, type(exc).__name__, exc)
