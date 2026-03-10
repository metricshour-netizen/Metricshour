"""
Macro Alert Checker — fires instantly after data ingestion AND on a daily fallback.

Called by:
  - world_bank_update task (after committing new WB data)
  - imf_update task (after committing new IMF data)
  - oecd_update task (after committing)
  - Celery Beat fallback: daily at 6:45am UTC (catches any missed updates)

For each active macro alert, checks the latest indicator value against the
user's threshold. Fires Telegram + email if condition is met and cooldown
has elapsed. Macro alerts are RECURRING — they stay active and re-fire
whenever the condition holds (respecting cooldown_days).
"""
import logging
from datetime import datetime, timedelta, timezone

from celery_app import app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, MacroAlert
from app.models.country import Country, CountryIndicator
from app.database import SessionLocal
from app.notifications import (
    send_telegram, send_email,
    build_macro_alert_telegram, build_macro_alert_email,
)

logger = logging.getLogger(__name__)


@app.task(name='tasks.macro_alert_checker.check_macro_alerts', bind=True, max_retries=2)
def check_macro_alerts(self):
    """Full check across all active macro alerts. Called after data ingestion + daily fallback."""
    db: Session = SessionLocal()
    try:
        fired = _run_checker(db)
        logger.info("Macro alert check complete. Fired: %d", fired)
        return f"ok: {fired} fired"
    except Exception as exc:
        logger.exception("Macro alert checker failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


def _run_checker(db: Session) -> int:
    active = db.execute(
        select(MacroAlert).where(MacroAlert.is_active == True)
    ).scalars().all()

    if not active:
        return 0

    # Build country_code → (country_id, country_name) map once
    countries = db.execute(select(Country.code, Country.id, Country.name)).all()
    code_to_id = {c.code: c.id for c in countries}
    code_to_name = {c.code: c.name for c in countries}

    now = datetime.now(timezone.utc)
    fired = 0

    for alert in active:
        # Check cooldown
        if alert.last_triggered_at:
            cooldown_until = alert.last_triggered_at + timedelta(days=alert.cooldown_days)
            if now < cooldown_until:
                continue

        country_id = code_to_id.get(alert.country_code)
        if not country_id:
            continue

        current_value = _get_latest_indicator(db, country_id, alert.indicator_name)
        if current_value is None:
            continue

        threshold = float(alert.threshold)
        triggered = (
            (alert.condition == "above" and current_value >= threshold) or
            (alert.condition == "below" and current_value <= threshold)
        )
        if not triggered:
            continue

        user = db.get(User, alert.user_id)
        if not user or not user.is_active:
            continue

        country_name = code_to_name.get(alert.country_code, alert.country_code)

        # Send Telegram
        if user.notify_telegram and user.telegram_chat_id:
            msg = build_macro_alert_telegram(
                country_name, alert.country_code,
                alert.indicator_name, alert.condition,
                threshold, current_value,
            )
            err = send_telegram(user.telegram_chat_id, msg)
            if err:
                logger.warning("Telegram failed uid=%s: %s", user.id, err)

        # Send email
        if user.notify_email and user.email:
            subject = f"📊 Macro Alert: {country_name} — MetricsHour"
            html = build_macro_alert_email(
                country_name, alert.country_code,
                alert.indicator_name, alert.condition,
                threshold, current_value,
            )
            err = send_email(user.email, subject, html)
            if err:
                logger.warning("Email failed uid=%s: %s", user.id, err)

        alert.last_triggered_at = now
        alert.trigger_count += 1
        fired += 1
        logger.info(
            "Macro alert fired: uid=%s country=%s indicator=%s value=%.4f threshold=%.4f",
            user.id, alert.country_code, alert.indicator_name, current_value, threshold,
        )

    if fired:
        db.commit()

    return fired


def _get_latest_indicator(db: Session, country_id: int, indicator_name: str) -> float | None:
    """Return the most recent value for this country+indicator."""
    row = db.execute(
        select(CountryIndicator.value)
        .where(
            CountryIndicator.country_id == country_id,
            CountryIndicator.indicator == indicator_name,
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None
