"""
Telegram social draft helpers — _handle_callback_query() is called from
the unified bot webhook at /api/alerts/telegram/webhook.

The old /api/telegram/webhook route has been removed. The single webhook URL is:
  https://api.metricshour.com/api/alerts/telegram/webhook

Re-register if needed:
  curl "https://api.telegram.org/bot{TOKEN}/setWebhook
        ?url=https://api.metricshour.com/api/alerts/telegram/webhook
        &secret_token={TELEGRAM_WEBHOOK_SECRET}"

Callback data format: social:{action}:{draft_key}
  action: linkedin | facebook | both | skip
"""
import json
import logging
import os
import sys

import requests
from fastapi import APIRouter, Request

# Workers path for social_poster
sys.path.insert(0, '/root/metricshour/workers')

from app.storage import get_redis

router = APIRouter()
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


def _tg_post(method: str, payload: dict, retries: int = 2) -> None:
    """POST to Telegram API with one retry on failure."""
    import time
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    for attempt in range(retries):
        try:
            requests.post(url, json=payload, timeout=5)
            return
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                log.warning("Telegram %s failed after %d attempts: %s", method, retries, exc)


def _answer_callback(callback_query_id: str, text: str) -> None:
    """Dismiss the loading spinner on the Telegram button."""
    _tg_post("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": False,
    })


def _edit_message(chat_id: int, message_id: int, text: str) -> None:
    """Update the original draft message to show status."""
    _tg_post("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text[:4000],
        "parse_mode": "HTML",
    })


def _send_message(chat_id: int, text: str) -> None:
    _tg_post("sendMessage", {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"})


def _handle_callback_query(callback: dict) -> dict:
    """Process a Telegram callback_query (inline button press from social drafts)."""
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
        raw = get_redis().get(draft_key)
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

    from tasks.social_poster import post_via_make, post_to_twitter, post_to_linkedin, post_to_facebook

    results = []
    facebook_text = draft.get("facebook", "") or draft.get("linkedin", "")  # reuse linkedin text if no dedicated fb copy

    # LinkedIn
    if action in ("linkedin", "both") and linkedin_text:
        err = post_to_linkedin(linkedin_text)
        if err and "not configured" not in err:
            if os.environ.get("MAKE_WEBHOOK_URL"):
                err2 = post_via_make("linkedin", linkedin_text, draft)
                if err2 and "not configured" not in err2:
                    _send_message(chat_id, f"💼 <b>LinkedIn (post manually):</b>\n\n{linkedin_text[:3000]}")
                    results.append("💼 LinkedIn failed — sent to chat")
                else:
                    results.append("💼 LinkedIn posted via Make.com ✓")
            else:
                _send_message(chat_id, f"💼 <b>LinkedIn (post manually):</b>\n\n{linkedin_text[:3000]}")
                results.append("💼 LinkedIn sent to chat")
        elif err and "not configured" in err:
            _send_message(chat_id, f"💼 <b>LinkedIn (post manually):</b>\n\n{linkedin_text[:3000]}")
            results.append("💼 LinkedIn not configured — sent to chat")
        else:
            results.append("💼 LinkedIn posted ✓")

    # Facebook
    if action in ("facebook", "both") and facebook_text:
        link = draft.get("url", "")
        err = post_to_facebook(facebook_text, link=link)
        if err and "not configured" not in err:
            if os.environ.get("MAKE_WEBHOOK_URL"):
                err2 = post_via_make("facebook", facebook_text, draft)
                if err2 and "not configured" not in err2:
                    _send_message(chat_id, f"📘 <b>Facebook (post manually):</b>\n\n{facebook_text[:3000]}")
                    results.append("📘 Facebook failed — sent to chat")
                else:
                    results.append("📘 Facebook posted via Make.com ✓")
            else:
                _send_message(chat_id, f"📘 <b>Facebook (post manually):</b>\n\n{facebook_text[:3000]}")
                results.append("📘 Facebook sent to chat")
        elif err and "not configured" in err:
            _send_message(chat_id, f"📘 <b>Facebook (post manually):</b>\n\n{facebook_text[:3000]}")
            results.append("📘 Facebook not configured — sent to chat")
        else:
            results.append("📘 Facebook posted ✓")

    # Twitter
    if action in ("twitter",) and twitter_text:
        err = post_to_twitter(twitter_text)
        if err and "not configured" not in err:
            if os.environ.get("MAKE_WEBHOOK_URL"):
                err2 = post_via_make("twitter", twitter_text, draft)
                if err2 and "not configured" not in err2:
                    _send_message(chat_id, f"🐦 <b>Twitter (post manually):</b>\n\n<code>{twitter_text}</code>")
                    results.append("🐦 Twitter failed — sent to chat")
                else:
                    results.append("🐦 Twitter posted via Make.com ✓")
            else:
                _send_message(chat_id, f"🐦 <b>Twitter (post manually):</b>\n\n<code>{twitter_text}</code>")
                results.append("🐦 Twitter sent to chat")
        elif err and "not configured" in err:
            _send_message(chat_id, f"🐦 <b>Twitter (post manually):</b>\n\n<code>{twitter_text}</code>")
            results.append("🐦 Twitter sent to chat")

    status = "\n".join(results) or "Nothing to post"
    _answer_callback(callback_id, status.replace("✓", "").strip()[:200])
    _edit_message(chat_id, message_id,
        f"✅ <b>{draft['entity']}</b>\n{status}"
    )

    return {"ok": True}
