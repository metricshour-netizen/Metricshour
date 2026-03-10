"""
Telegram webhook — handles inline button callbacks from social content drafts.

Register once (run from shell):
  curl "https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://api.metricshour.com/api/telegram/webhook"

Callback data format: social:{action}:{draft_key}
  action: twitter | linkedin | both | skip
"""
import json
import logging
import os
import sys

import redis as redis_lib
import requests
from fastapi import APIRouter, Request

# Workers path for social_poster
sys.path.insert(0, '/root/metricshour/workers')

router = APIRouter()
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
REDIS_URL = os.environ.get("REDIS_URL", "")


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)


def _answer_callback(callback_query_id: str, text: str) -> None:
    """Dismiss the loading spinner on the Telegram button."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text, "show_alert": False},
            timeout=5,
        )
    except Exception:
        pass


def _edit_message(chat_id: int, message_id: int, text: str) -> None:
    """Update the original draft message to show status."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text[:4000],
                "parse_mode": "HTML",
            },
            timeout=5,
        )
    except Exception:
        pass


def _send_message(chat_id: int, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:
        pass


@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    # Validate secret token header if set
    if TELEGRAM_WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != TELEGRAM_WEBHOOK_SECRET:
            return {"ok": False}

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    callback = update.get("callback_query")
    if not callback:
        return {"ok": True}

    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    data = callback.get("data", "")

    if not data.startswith("social:"):
        return {"ok": True}

    # Parse: social:{action}:{draft_key}
    parts = data.split(":", 2)
    if len(parts) < 3:
        return {"ok": True}

    _, action, draft_key = parts

    if action == "skip":
        _answer_callback(callback_id, "Skipped ✓")
        _edit_message(chat_id, message_id, "❌ <i>Draft skipped.</i>")
        return {"ok": True}

    # Retrieve draft from Redis
    try:
        raw = _redis().get(draft_key)
    except Exception as e:
        _answer_callback(callback_id, "Redis error")
        log.warning("Redis get draft failed: %s", e)
        return {"ok": True}

    if not raw:
        _answer_callback(callback_id, "Draft expired (>48h)")
        _edit_message(chat_id, message_id, "⏰ <i>Draft expired.</i>")
        return {"ok": True}

    draft = json.loads(raw)
    twitter_text = draft.get("twitter", "")
    linkedin_text = draft.get("linkedin", "")

    from tasks.social_poster import post_via_make, post_to_twitter

    results = []

    # Route through Make.com if configured (handles LinkedIn + Facebook + Twitter)
    if os.environ.get("MAKE_WEBHOOK_URL"):
        platform = action  # twitter | linkedin | both
        text = twitter_text if action == "twitter" else linkedin_text
        err = post_via_make(platform, text, draft)
        if err and "not configured" not in err:
            results.append(f"Make.com failed: {err}")
            # Fallback: send to chat
            _send_message(chat_id, f"📋 <b>Post manually:</b>\n\n{text[:3000]}")
        else:
            label = {"twitter": "🐦 Twitter", "linkedin": "💼 LinkedIn + Facebook", "both": "🐦💼 All platforms"}.get(action, action)
            results.append(f"{label} posted via Make.com ✓")
    else:
        # Direct posting fallback
        if action in ("twitter", "both") and twitter_text:
            err = post_to_twitter(twitter_text)
            if err:
                _send_message(chat_id, f"🐦 <b>Twitter (post manually):</b>\n\n<code>{twitter_text}</code>")
                results.append("🐦 Sent to chat (configure MAKE_WEBHOOK_URL or Twitter API)")
            else:
                results.append("🐦 Posted to Twitter ✓")

        if action in ("linkedin", "both") and linkedin_text:
            _send_message(chat_id, f"💼 <b>LinkedIn (post manually):</b>\n\n{linkedin_text}")
            results.append("💼 Sent to chat (add MAKE_WEBHOOK_URL to automate)")

    status = "\n".join(results) or "Nothing to post"
    _answer_callback(callback_id, status.replace("✓", "").strip()[:200])
    _edit_message(chat_id, message_id,
        f"✅ <b>{draft['entity']}</b>\n{status}"
    )

    return {"ok": True}
