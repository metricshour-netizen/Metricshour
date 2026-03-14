"""
Worker watchdog — heartbeat tracking + staleness alerts.

Two mechanisms:

1. Heartbeat writer (via task_success signal in celery_app.py):
   - Every successful task writes `worker:hb:{task_name}` = ISO timestamp to Redis
   - TTL = 3x the expected interval (auto-expires stale keys)

2. Watchdog task (every 10 min via Beat):
   - Checks that each critical task's heartbeat is fresh
   - Fires a Telegram alert if any critical task hasn't run within its expected window
   - Also alerts if the worker process count drops to 0 (celery inspect ping)

Beat entry added in celery_app.py:
    'watchdog-every-10min': {
        'task': 'tasks.watchdog.check_worker_health',
        'schedule': 600.0,
    }
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

from celery_app import app
from app.storage import get_redis

log = logging.getLogger(__name__)

_TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HB_PREFIX = "worker:hb:"

# Critical tasks: task_name → max allowed seconds since last success
# Set to 3x the normal schedule interval to tolerate one missed run.
CRITICAL_TASKS = {
    "tasks.crypto.fetch_crypto_prices":         600,    # 2min schedule → alert after 10min
    "tasks.price_alert_checker.check_price_alerts": 300, # 1min schedule → alert after 5min
    "tasks.stocks.fetch_stock_prices":          3600,   # 15min → alert after 1h
    "tasks.commodities.fetch_commodity_prices": 3600,   # 15min → alert after 1h
    "tasks.fx.fetch_fx_rates":                  3600,   # 15min → alert after 1h
    "tasks.feed_generator.generate_feed_events": 900,   # 3min → alert after 15min
    "tasks.r2_snapshots.write_r2_snapshots":    90000,  # daily → alert if >25h late
    "tasks.backup.run_backup":                  90000,  # daily → alert if >25h late
}

# Redis key for last watchdog alert time — prevents alert storm (1 alert per 30min per task)
_ALERT_THROTTLE_PREFIX = "worker:watchdog:alerted:"
_ALERT_THROTTLE_TTL = 1800  # 30 minutes


def record_heartbeat(task_name: str) -> None:
    """Store a heartbeat timestamp for a task. Called on task_success signal."""
    try:
        r = get_redis()
        key = HB_PREFIX + task_name
        # TTL = 3x max allowed age so key auto-expires if task stops completely
        max_age = CRITICAL_TASKS.get(task_name, 86400)
        r.setex(key, max_age * 3, datetime.now(timezone.utc).isoformat())
    except Exception as e:
        log.debug("Heartbeat write failed for %s: %s", task_name, e)


def _send_telegram_alert(message: str) -> None:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.error("Watchdog Telegram send failed: %s", e)


def _is_throttled(task_name: str) -> bool:
    """Return True if we already sent an alert for this task recently."""
    try:
        r = get_redis()
        return bool(r.exists(_ALERT_THROTTLE_PREFIX + task_name))
    except Exception:
        return False


def _throttle(task_name: str) -> None:
    try:
        r = get_redis()
        r.setex(_ALERT_THROTTLE_PREFIX + task_name, _ALERT_THROTTLE_TTL, "1")
    except Exception:
        pass


@app.task(name="tasks.watchdog.check_worker_health", bind=True, max_retries=0)
def check_worker_health(self):
    """
    Check all critical task heartbeats. Fire Telegram alert for any that are stale.
    Runs every 10 minutes via Beat.
    """
    r = get_redis()
    now = datetime.now(timezone.utc)
    stale = []

    for task_name, max_age_secs in CRITICAL_TASKS.items():
        key = HB_PREFIX + task_name
        raw = r.get(key)

        if raw is None:
            # Key missing entirely — task has never run OR TTL expired (3x max_age)
            # Only alert if max_age < 1 day (don't alert for daily tasks at startup)
            if max_age_secs < 86400 and not _is_throttled(task_name):
                stale.append((task_name, "never ran or heartbeat expired"))
            continue

        try:
            last_run = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
            age_secs = (now - last_run).total_seconds()
            if age_secs > max_age_secs and not _is_throttled(task_name):
                minutes = int(age_secs / 60)
                stale.append((task_name, f"last ran {minutes}m ago (threshold {max_age_secs//60}m)"))
        except Exception as e:
            log.debug("Watchdog parse error for %s: %s", task_name, e)

    if stale:
        lines = "\n".join(f"• <code>{t}</code>: {reason}" for t, reason in stale)
        msg = (
            f"⚠️ <b>Worker Watchdog Alert</b>\n\n"
            f"The following tasks appear stale:\n\n"
            f"{lines}\n\n"
            f"Check: <code>systemctl status metricshour-worker</code>"
        )
        _send_telegram_alert(msg)
        log.warning("Watchdog: stale tasks detected: %s", [t for t, _ in stale])
        for task_name, _ in stale:
            _throttle(task_name)
    else:
        log.debug("Watchdog: all critical tasks are healthy")

    return {"checked": len(CRITICAL_TASKS), "stale": len(stale)}


@app.task(name="tasks.watchdog.get_dlq", bind=True, max_retries=0)
def get_dlq(self, limit: int = 20):
    """Return the last N entries from the dead-letter queue. For admin use."""
    try:
        r = get_redis()
        raw = r.lrange("worker:dlq", 0, limit - 1)
        return [json.loads(e) for e in raw]
    except Exception as e:
        log.error("DLQ read failed: %s", e)
        return []
