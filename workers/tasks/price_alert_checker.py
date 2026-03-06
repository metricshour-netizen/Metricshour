"""
Price Alert Checker — runs every minute via Celery Beat.

Loads all active price alerts, compares against latest prices,
fires Telegram + email notifications, and marks alerts as triggered.
"""
import logging
from datetime import datetime, timedelta, timezone

from celery_app import app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, PriceAlert, AlertDelivery
from app.models.asset import Asset, Price
from app.database import SessionLocal
from app.notifications import (
    send_telegram, send_email,
    build_alert_telegram, build_alert_email,
)

logger = logging.getLogger(__name__)


@app.task(name='tasks.price_alert_checker.check_price_alerts', bind=True, max_retries=2)
def check_price_alerts(self):
    """Check all active price alerts and fire notifications when thresholds are crossed."""
    db: Session = SessionLocal()
    try:
        _run_checker(db)
    except Exception as exc:
        logger.exception("Price alert checker failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


def _run_checker(db: Session):
    # Load all active (not yet triggered) alerts with user eager-loaded
    active_alerts = db.execute(
        select(PriceAlert)
        .where(PriceAlert.is_active == True, PriceAlert.triggered_at == None)
    ).scalars().all()

    if not active_alerts:
        return

    # Batch-load latest prices for all relevant asset IDs
    asset_ids = list({a.asset_id for a in active_alerts})
    latest_prices: dict[int, float] = _get_latest_prices(db, asset_ids)

    now = datetime.now(timezone.utc)
    triggered_count = 0

    for alert in active_alerts:
        current_price = latest_prices.get(alert.asset_id)
        if current_price is None:
            continue

        fired = (
            (alert.condition == "above" and current_price >= alert.target_price) or
            (alert.condition == "below" and current_price <= alert.target_price)
        )
        if not fired:
            continue

        # Prevent duplicate delivery for this alert within 1 hour
        recent = db.execute(
            select(AlertDelivery).where(
                AlertDelivery.alert_id == alert.id,
                AlertDelivery.triggered_at >= now - timedelta(hours=1),
            )
        ).scalar_one_or_none()
        if recent:
            continue

        user = db.get(User, alert.user_id)
        asset = db.get(Asset, alert.asset_id)
        if not user or not asset:
            continue

        symbol = asset.symbol
        name = asset.name
        condition = alert.condition
        target = alert.target_price

        # Send Telegram
        if user.notify_telegram and user.telegram_chat_id:
            msg = build_alert_telegram(symbol, name, condition, target, current_price)
            err = send_telegram(user.telegram_chat_id, msg)
            _record_delivery(db, alert.id, user.id, "telegram", current_price, now, err)

        # Send Email
        if user.notify_email and user.email:
            subject = f"🚨 {symbol} Price Alert — MetricsHour"
            html = build_alert_email(symbol, name, condition, target, current_price)
            err = send_email(user.email, subject, html)
            _record_delivery(db, alert.id, user.id, "email", current_price, now, err)

        # Mark alert as triggered (one-shot — user re-creates if they want another)
        alert.triggered_at = now
        alert.is_active = False
        triggered_count += 1

    if triggered_count:
        db.commit()
        logger.info("Price alerts fired: %d", triggered_count)


def _get_latest_prices(db: Session, asset_ids: list[int]) -> dict[int, float]:
    """Return {asset_id: latest close price} for the given asset IDs."""
    if not asset_ids:
        return {}
    from sqlalchemy import func
    latest_ts_sq = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .where(Price.asset_id.in_(asset_ids))
        .group_by(Price.asset_id)
        .subquery()
    )
    rows = db.execute(
        select(Price.asset_id, Price.close).join(
            latest_ts_sq,
            (Price.asset_id == latest_ts_sq.c.asset_id) &
            (Price.timestamp == latest_ts_sq.c.max_ts),
        )
    ).all()
    return {r.asset_id: r.close for r in rows}


def _record_delivery(
    db: Session,
    alert_id: int,
    user_id: int,
    channel: str,
    price: float,
    triggered_at: datetime,
    error: str | None,
):
    delivery = AlertDelivery(
        alert_id=alert_id,
        user_id=user_id,
        channel=channel,
        price_at_trigger=price,
        triggered_at=triggered_at,
        delivered_at=datetime.now(timezone.utc) if not error else None,
        error=error,
    )
    db.add(delivery)
