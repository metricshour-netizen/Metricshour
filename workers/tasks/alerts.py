"""
Celery failure alerting.

Wired via the task_failure signal in celery_app.py — no changes needed in
individual task files. Fires only on FINAL failures (after all retries exhausted).

Delivery:
  1. Structured log to /var/log/metricshour/celery-failures.log (always)
  2. Discord webhook embed (if DISCORD_WEBHOOK_URL is set in .env)

Set DISCORD_WEBHOOK_URL in backend/.env to enable Discord alerts.
"""

import logging
import os
import socket
import traceback
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

FAILURE_LOG = "/var/log/metricshour/celery-failures.log"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Only alert on final failure — not on every retry attempt
_RETRY_EXC_NAMES = {"MaxRetriesExceededError", "Retry"}


def _is_final_failure(exc: BaseException) -> bool:
    """True when the task has exhausted retries (or failed without retry)."""
    return type(exc).__name__ not in _RETRY_EXC_NAMES


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


def _discord_embed(task_name: str, exc: BaseException, tb: str, retries: int) -> dict:
    """Build a Discord webhook payload with a red embed."""
    host = socket.gethostname()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Trim traceback to last 10 lines so it fits in Discord's 1024-char field limit
    tb_lines = tb.strip().splitlines()
    tb_short = "\n".join(tb_lines[-10:])
    if len(tb_short) > 900:
        tb_short = "..." + tb_short[-900:]

    return {
        "embeds": [{
            "title": "Celery Task Failed",
            "color": 0xE53935,  # red
            "fields": [
                {"name": "Task", "value": f"`{task_name}`", "inline": True},
                {"name": "Retries", "value": str(retries), "inline": True},
                {"name": "Host", "value": host, "inline": True},
                {"name": "Exception", "value": f"`{type(exc).__name__}: {str(exc)[:200]}`", "inline": False},
                {"name": "Traceback", "value": f"```\n{tb_short}\n```", "inline": False},
            ],
            "footer": {"text": f"metricshour · {now}"},
        }]
    }


def _send_discord(task_name: str, exc: BaseException, tb: str, retries: int) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        payload = _discord_embed(task_name, exc, tb, retries)
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Discord alert sent for %s", task_name)
    except Exception as e:
        log.error("Failed to send Discord alert: %s", e)


def on_task_failure(task_name: str, exc: BaseException, retries: int = 0) -> None:
    """
    Call this from the task_failure Celery signal handler.
    Logs the failure and sends a Discord alert if configured.
    """
    tb = traceback.format_exc()
    _log_failure(task_name, exc, tb, retries)
    _send_discord(task_name, exc, tb, retries)
    log.error("FINAL FAILURE: %s after %d retries — %s: %s", task_name, retries, type(exc).__name__, exc)
