"""
Macro Alert Checker — fires instantly after data ingestion AND on a daily fallback.

Called by:
  - world_bank_update task (after committing new WB data)
  - imf_update task (after committing new IMF data)
  - oecd_update task (after committing)
  - Celery Beat fallback: daily at 6:45am UTC (catches any missed updates)

Smart alerts: when an alert fires, Gemini 2.5 Flash Lite generates 2-sentence
context (trend + investor implication) inserted into both Telegram + email.
Cost: ~$0.00001 per alert fired (only runs when threshold is actually crossed).
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from celery_app import app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, MacroAlert
from app.models.country import Country, CountryIndicator
from app.database import SessionLocal
from app.notifications import (
    send_macro_alert_via_n8n,
    INDICATOR_LABELS,
)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


_ALERT_SYSTEM = (
    "You are a quantitative macro analyst writing concise investor alerts. "
    "Use only the data provided — never invent statistics. "
    "Active voice only. Assert — never hedge. "
    "Do not use: could, may, might, would likely, appears to, seems to. "
    "No filler. No greeting. No sign-off. Begin immediately with the data point."
)


def _generate_smart_context(
    country_name: str,
    indicator_label: str,
    current: float,
    threshold: float,
    condition: str,
    history: list[tuple[int, float]],  # [(year, value), ...] newest first
) -> str | None:
    """Call Gemini 2.5 Flash Lite to produce 2-sentence alert context. Returns None on any failure."""
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types as genai_types

        hist_str = ", ".join(f"{yr}: {val:.2f}" for yr, val in history) if history else "no history"
        direction = "above" if condition == "above" else "below"

        prompt = (
            f"{country_name} — {indicator_label}: current value {current:.2f}, "
            f"crossed {direction} threshold {threshold:.2f}. "
            f"Recent history: {hist_str}. "
            f"Write exactly 2 sentences: "
            f"sentence 1 states what this trend means using the historical context and specific numbers; "
            f"sentence 2 gives the single most direct market or portfolio implication. "
            f"Total: 30-50 words."
        )

        client = genai.Client(api_key=GEMINI_API_KEY)
        r = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_ALERT_SYSTEM,
                max_output_tokens=120,
                temperature=0.2,
            ),
        )
        text = (r.text or "").strip()
        return text if len(text) > 20 else None
    except Exception as e:
        logger.warning("Gemini context generation failed: %s", e)
        return None


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

    # Build country_code → (id, name) maps once
    countries = db.execute(select(Country.code, Country.id, Country.name)).all()
    code_to_id = {c.code: c.id for c in countries}
    code_to_name = {c.code: c.name for c in countries}

    now = datetime.now(timezone.utc)
    fired = 0

    for alert in active:
        # Cooldown check
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
        label, _ = INDICATOR_LABELS.get(alert.indicator_name, (alert.indicator_name, ""))

        # Fetch recent history for smart context (last 5 years, newest first)
        history = _get_history(db, country_id, alert.indicator_name, limit=5)

        # Generate smart 2-sentence context via Gemini Flash Lite
        context = _generate_smart_context(
            country_name, label, current_value, threshold, alert.condition, history
        )

        # Dispatch via n8n (with direct fallback if n8n is unreachable)
        err = send_macro_alert_via_n8n(
            user_email=user.email,
            telegram_chat_id=user.telegram_chat_id,
            notify_telegram=user.notify_telegram,
            notify_email=user.notify_email,
            country_name=country_name,
            country_code=alert.country_code,
            indicator_name=alert.indicator_name,
            condition=alert.condition,
            threshold=threshold,
            current_value=current_value,
            context=context,
        )
        if err:
            # All channels failed — don't start cooldown, retry next run
            logger.error(
                "Macro alert NOT delivered uid=%s country=%s indicator=%s: %s",
                user.id, alert.country_code, alert.indicator_name, err,
            )
            continue

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


def _get_history(
    db: Session, country_id: int, indicator_name: str, limit: int = 5
) -> list[tuple[int, float]]:
    """Return last N (year, value) pairs, newest first."""
    rows = db.execute(
        select(CountryIndicator.period_date, CountryIndicator.value)
        .where(
            CountryIndicator.country_id == country_id,
            CountryIndicator.indicator == indicator_name,
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(limit)
    ).all()
    return [(r.period_date.year, float(r.value)) for r in rows]
