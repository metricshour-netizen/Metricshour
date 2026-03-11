"""
Price alert CRUD + Telegram account linking.

GET    /api/alerts                           - list user's active alerts
POST   /api/alerts                           - create alert
DELETE /api/alerts/{id}                      - delete alert
GET    /api/alerts/deliveries                - delivery history (last 30)
GET    /api/alerts/prefs                     - get notification prefs + telegram status
PUT    /api/alerts/prefs                     - update notify_telegram / notify_email
POST   /api/alerts/telegram/generate-code    - generate 6-char link code (10min TTL)
POST   /api/alerts/telegram/disconnect       - remove telegram_chat_id
POST   /api/alerts/telegram/webhook          - Telegram bot webhook (no auth, secret header)
"""
import os
import secrets
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.database import get_db
from app.limiter import limiter
from app.models.user import User, PriceAlert, AlertDelivery, MacroAlert
from app.notifications import INDICATOR_LABELS
from app.models.asset import Asset
from app.routers.auth import get_current_user
from app.storage import redis_json_set, redis_json_get

router = APIRouter(prefix="/alerts", tags=["alerts"])

TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
_CODE_TTL = 600  # 10 minutes


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AlertIn(BaseModel):
    asset_id: int
    condition: str       # 'above' | 'below'
    target_price: float


class MacroAlertIn(BaseModel):
    country_code: str    # ISO2 e.g. 'US'
    indicator_name: str  # e.g. 'government_debt_gdp_pct'
    condition: str       # 'above' | 'below'
    threshold: float
    cooldown_days: int = 7


class PrefsIn(BaseModel):
    notify_telegram: bool | None = None
    notify_email: bool | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gen_code(length: int = 6) -> str:
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))


def _alert_dict(a: PriceAlert, db: Session) -> dict:
    asset = db.get(Asset, a.asset_id)
    return {
        "id": a.id,
        "asset": {"id": asset.id, "symbol": asset.symbol, "name": asset.name} if asset else None,
        "condition": a.condition,
        "target_price": a.target_price,
        "is_active": a.is_active,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "created_at": a.created_at.isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    alerts = db.execute(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id)
        .order_by(desc(PriceAlert.created_at))
    ).scalars().all()
    return [_alert_dict(a, db) for a in alerts]


@router.post("", status_code=201)
def create_alert(
    body: AlertIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.condition not in ("above", "below"):
        raise HTTPException(status_code=422, detail="condition must be 'above' or 'below'")
    if body.target_price <= 0:
        raise HTTPException(status_code=422, detail="target_price must be positive")

    asset = db.get(Asset, body.asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Limit free tier to 5 active alerts
    active_count = db.execute(
        select(PriceAlert).where(
            PriceAlert.user_id == current_user.id,
            PriceAlert.is_active == True,
        )
    ).scalars().all()
    if current_user.tier == "free" and len(active_count) >= 5:
        raise HTTPException(status_code=422, detail="Free tier limited to 5 active alerts. Upgrade for unlimited.")

    alert = PriceAlert(
        user_id=current_user.id,
        asset_id=body.asset_id,
        condition=body.condition,
        target_price=body.target_price,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_dict(alert, db)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.execute(
        select(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()


@router.get("/deliveries")
def list_deliveries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        select(AlertDelivery)
        .where(AlertDelivery.user_id == current_user.id)
        .order_by(desc(AlertDelivery.triggered_at))
        .limit(30)
    ).scalars().all()
    return [
        {
            "id": d.id,
            "alert_id": d.alert_id,
            "channel": d.channel,
            "price_at_trigger": d.price_at_trigger,
            "triggered_at": d.triggered_at.isoformat(),
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            "error": d.error,
        }
        for d in rows
    ]


@router.get("/prefs")
def get_prefs(
    current_user: User = Depends(get_current_user),
) -> dict:
    return {
        "notify_telegram": current_user.notify_telegram,
        "notify_email": current_user.notify_email,
        "telegram_connected": bool(current_user.telegram_chat_id),
    }


@router.put("/prefs")
def update_prefs(
    body: PrefsIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.notify_telegram is not None:
        current_user.notify_telegram = body.notify_telegram
    if body.notify_email is not None:
        current_user.notify_email = body.notify_email
    db.commit()
    return {
        "notify_telegram": current_user.notify_telegram,
        "notify_email": current_user.notify_email,
        "telegram_connected": bool(current_user.telegram_chat_id),
    }


@router.post("/telegram/generate-code")
@limiter.limit("10/minute")
def generate_telegram_code(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a 6-char one-time code. User sends it to the bot to link their account."""
    code = _gen_code()
    redis_json_set(f"tg:link:{code}", {"uid": current_user.id}, ttl_seconds=_CODE_TTL)
    return {"code": code, "expires_in_seconds": _CODE_TTL}


@router.post("/telegram/disconnect", status_code=204)
def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.telegram_chat_id = None
    db.commit()


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """
    Telegram bot webhook. Telegram calls this on every message.
    Register with: POST https://api.telegram.org/bot{TOKEN}/setWebhook
                       ?url=https://api.metricshour.com/api/alerts/telegram/webhook
                       &secret_token={TELEGRAM_WEBHOOK_SECRET}
    """
    # Always require the secret header — reject requests if secret is not configured
    # (this prevents the webhook from being open if the env var is accidentally cleared)
    if not TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    if x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    raw = await request.body()
    if len(raw) > 65_536:  # 64 KB max — Telegram payloads are always tiny
        raise HTTPException(status_code=413, detail="Payload too large")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Route callback_query updates to the social draft handler
    # (social content drafts send inline buttons; those arrive as callback_query)
    if body.get("callback_query"):
        from app.routers.telegram_webhook import _handle_callback_query
        return _handle_callback_query(body["callback_query"])

    message = body.get("message") or body.get("my_chat_member", {}).get("message")
    if not message:
        return {"ok": True}

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()

    # Handle /start or /connect commands with a code
    # Supports: "/start CODE", "/connect CODE", or just "CODE"
    code = None
    if text.startswith("/start") or text.startswith("/connect"):
        parts = text.split()
        if len(parts) >= 2:
            code = parts[1].upper()
    elif len(text) == 6 and text.isalnum():
        code = text.upper()

    if not code:
        _send_telegram_reply(chat_id, (
            "👋 <b>MetricsHour Alerts</b>\n\n"
            "To connect your account:\n"
            "1. Go to <b>metricshour.com/alerts</b>\n"
            "2. Click <b>Connect Telegram</b>\n"
            "3. Send me the 6-character code shown\n\n"
            "Then you'll receive price alerts here instantly! 🚀"
        ))
        return {"ok": True}

    cached = redis_json_get(f"tg:link:{code}")
    if not cached:
        _send_telegram_reply(chat_id, "❌ Code not found or expired. Please generate a new one at metricshour.com/alerts")
        return {"ok": True}

    user = db.get(User, int(cached["uid"]))
    if not user:
        _send_telegram_reply(chat_id, "❌ Account not found.")
        return {"ok": True}

    # Link the account
    user.telegram_chat_id = chat_id
    db.commit()

    first_name = message.get("from", {}).get("first_name", "there")
    _send_telegram_reply(chat_id, (
        f"✅ <b>Connected, {first_name}!</b>\n\n"
        f"Your Telegram is now linked to <b>{user.email}</b>.\n"
        f"You'll receive price alerts here instantly.\n\n"
        f"<a href=\"https://metricshour.com/alerts\">Manage your alerts →</a>"
    ))
    return {"ok": True}


# ── Macro Alert routes ────────────────────────────────────────────────────────

def _macro_dict(a: MacroAlert) -> dict:
    label, unit = INDICATOR_LABELS.get(a.indicator_name, (a.indicator_name, ""))
    return {
        "id": a.id,
        "country_code": a.country_code,
        "indicator_name": a.indicator_name,
        "indicator_label": label,
        "indicator_unit": unit,
        "condition": a.condition,
        "threshold": float(a.threshold),
        "is_active": a.is_active,
        "cooldown_days": a.cooldown_days,
        "last_triggered_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        "trigger_count": a.trigger_count,
        "created_at": a.created_at.isoformat(),
    }


@router.get("/macro")
def list_macro_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    alerts = db.execute(
        select(MacroAlert)
        .where(MacroAlert.user_id == current_user.id)
        .order_by(desc(MacroAlert.created_at))
    ).scalars().all()
    return [_macro_dict(a) for a in alerts]


@router.post("/macro", status_code=201)
def create_macro_alert(
    body: MacroAlertIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.condition not in ("above", "below"):
        raise HTTPException(status_code=422, detail="condition must be 'above' or 'below'")
    if body.indicator_name not in INDICATOR_LABELS:
        raise HTTPException(status_code=422, detail="indicator_name not supported")
    body.country_code = body.country_code.upper()

    # Free tier: max 3 macro alerts
    if current_user.tier == "free":
        active = db.execute(
            select(MacroAlert).where(
                MacroAlert.user_id == current_user.id,
                MacroAlert.is_active == True,
            )
        ).scalars().all()
        if len(active) >= 3:
            raise HTTPException(
                status_code=422,
                detail="Free tier limited to 3 macro alerts. Upgrade to Pro for unlimited."
            )

    alert = MacroAlert(
        user_id=current_user.id,
        country_code=body.country_code,
        indicator_name=body.indicator_name,
        condition=body.condition,
        threshold=body.threshold,
        cooldown_days=max(1, min(body.cooldown_days, 90)),
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _macro_dict(alert)


@router.delete("/macro/{alert_id}", status_code=204)
def delete_macro_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.execute(
        select(MacroAlert).where(
            MacroAlert.id == alert_id,
            MacroAlert.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()


@router.get("/indicators")
def list_alertable_indicators() -> dict:
    """Return all indicators that can be used in macro alerts."""
    return {
        k: {"label": v[0], "unit": v[1]}
        for k, v in INDICATOR_LABELS.items()
    }


def _send_telegram_reply(chat_id: str, text: str):
    """Fire-and-forget Telegram message from within the webhook handler."""
    import requests as req
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:
        pass
