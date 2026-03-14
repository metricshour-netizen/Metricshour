"""
Newsletter subscription — POST /api/newsletter/subscribe
                          GET  /api/newsletter/unsubscribe?token=...

No auth required. Rate-limited at the Cloudflare edge.
"""
import secrets
import re
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.limiter import limiter
from app.models.user import NewsletterSubscriber
from app.notifications import send_newsletter_welcome

logger = logging.getLogger(__name__)
router = APIRouter()

_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class SubscribeRequest(BaseModel):
    email: str
    source: str = "unknown"


@router.post("/newsletter/subscribe", status_code=201)
@limiter.limit("10/minute")
def subscribe(request: Request, body: SubscribeRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address")

    existing = db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    ).scalar_one_or_none()

    if existing:
        if existing.is_active:
            return {"status": "already_subscribed"}
        # Re-subscribe
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.source = body.source
        db.commit()
        send_newsletter_welcome(email, existing.token)
        return {"status": "resubscribed"}

    token = secrets.token_hex(32)
    sub = NewsletterSubscriber(
        email=email,
        source=body.source[:50],
        is_active=True,
        token=token,
        subscribed_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    db.commit()
    send_newsletter_welcome(email, token)
    logger.info("New newsletter subscriber: %s (source=%s)", email, body.source)
    return {"status": "subscribed"}


@router.get("/newsletter/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    sub = db.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.token == token)
    ).scalar_one_or_none()

    if not sub:
        return HTMLResponse(_unsubscribe_page("Link not found or already used."), status_code=404)

    if not sub.is_active:
        return HTMLResponse(_unsubscribe_page("You're already unsubscribed."))

    sub.is_active = False
    sub.unsubscribed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Newsletter unsubscribe: %s", sub.email)
    return HTMLResponse(_unsubscribe_page("You've been unsubscribed.", success=True))


def _unsubscribe_page(message: str, success: bool = False) -> str:
    color = "#10b981" if success else "#9ca3af"
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>MetricsHour — Unsubscribe</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:40px 20px;background:#0a0e1a;font-family:sans-serif;text-align:center;">
  <a href="https://metricshour.com" style="font-size:20px;font-weight:800;color:#10b981;letter-spacing:1px;text-decoration:none;">METRICSHOUR</a>
  <p style="font-size:16px;color:{color};margin:32px 0 16px 0;">{message}</p>
  <a href="https://metricshour.com" style="color:#6b7280;font-size:13px;">← Back to MetricsHour</a>
</body>
</html>"""
