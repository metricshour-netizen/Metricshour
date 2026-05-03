"""
Email-only asset alert capture — no authentication required.

POST /api/email-alerts          — subscribe email to asset alerts
GET  /api/email-alerts/unsubscribe  — unsubscribe via token link (in email)
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.user import EmailAlert
from fastapi import Request

router = APIRouter(prefix="/email-alerts", tags=["email-alerts"])


class EmailAlertIn(BaseModel):
    email: EmailStr
    asset_symbol: str
    asset_name: str = ""
    asset_type: str = "stock"


@router.post("")
@limiter.limit("10/minute")
def create_email_alert(
    payload: EmailAlertIn,
    request: Request,
    db: Session = Depends(get_db),
):
    symbol = payload.asset_symbol.upper().strip()

    # Deduplicate: one active alert per email per asset
    existing = db.execute(
        select(EmailAlert).where(
            EmailAlert.email == payload.email,
            EmailAlert.asset_symbol == symbol,
            EmailAlert.is_active == True,
        )
    ).scalar_one_or_none()

    if existing:
        return {"status": "exists", "message": "Alert already active for this asset"}

    alert = EmailAlert(
        email=payload.email,
        asset_symbol=symbol,
        asset_name=payload.asset_name[:200] if payload.asset_name else "",
        asset_type=payload.asset_type,
        is_active=True,
        unsubscribe_token=secrets.token_urlsafe(32),
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    return {"status": "created", "message": "Alert created"}


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = Query(...), db: Session = Depends(get_db)):
    alert = db.execute(
        select(EmailAlert).where(EmailAlert.unsubscribe_token == token)
    ).scalar_one_or_none()

    if not alert:
        return HTMLResponse(
            content=_html_page("Link not found", "This unsubscribe link is invalid or has already been used."),
            status_code=404,
        )

    alert.is_active = False
    db.commit()

    name = alert.asset_name or alert.asset_symbol
    return HTMLResponse(content=_html_page(
        "Unsubscribed",
        f"You've been unsubscribed from alerts for <strong>{name}</strong>. "
        f"You won't receive any more notifications for this asset.",
    ))


def _html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — MetricsHour</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0a0d14; color: #d1d5db;
            display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
    .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 12px;
              padding: 2rem; max-width: 420px; text-align: center; }}
    h1 {{ color: #fff; font-size: 1.25rem; margin-bottom: 0.75rem; }}
    p {{ color: #9ca3af; font-size: 0.875rem; line-height: 1.6; }}
    a {{ color: #10b981; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>{body}</p>
    <p style="margin-top:1.5rem"><a href="https://metricshour.com">← Back to MetricsHour</a></p>
  </div>
</body>
</html>"""
