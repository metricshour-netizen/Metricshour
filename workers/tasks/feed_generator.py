"""
Feed event generator — detects market-moving events and writes feed cards.

Runs every 15 minutes via Celery Beat.

Events generated:
  price_move     — asset price changed ≥2% in the last 15 minutes
  macro_release  — a new economic indicator row was inserted in the last 24 hours
  rate_decision  — placeholder for central bank rate change events (future: RSS feed)

importance_score logic:
  price_move:    floor(abs(change_pct)) capped at 10  (e.g. 5.2% → 5, 11% → 10)
  macro_release: based on indicator tier (see INDICATOR_IMPORTANCE below)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price
from app.models.country import CountryIndicator
from app.models.feed import FeedEvent

log = logging.getLogger(__name__)

# ── Indicator importance weights (0–10) ───────────────────────────────────────
# Higher = more important; drives feed card ranking for non-personalised users.
INDICATOR_IMPORTANCE: dict[str, float] = {
    "interest_rate":             10.0,
    "gdp_growth_rate":           9.0,
    "inflation_rate":            9.0,
    "unemployment_rate":         8.0,
    "current_account_balance":   7.0,
    "government_debt_gdp":       7.0,
    "budget_balance_gdp":        6.0,
    "trade_balance":             6.0,
    "gdp_per_capita":            5.0,
    "industrial_production":     5.0,
    "retail_sales":              5.0,
    "consumer_confidence":       4.0,
}
DEFAULT_INDICATOR_IMPORTANCE = 3.0

# Only generate price-move events if the absolute change meets this threshold
PRICE_MOVE_THRESHOLD_PCT = 2.0


@app.task(name='tasks.feed_generator.generate_feed_events', bind=True, max_retries=2)
def generate_feed_events(self):
    db = SessionLocal()
    try:
        _generate_price_moves(db)
        _generate_macro_releases(db)
        db.commit()
        log.info("feed_generator: completed successfully")
    except Exception as exc:
        db.rollback()
        log.error("feed_generator: failed — %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


# ── Price move events ─────────────────────────────────────────────────────────

def _generate_price_moves(db) -> None:
    """
    Compare the latest price to the price 15 minutes earlier.
    If abs(change_pct) >= threshold, create/update a feed event.
    De-duplicate: one price_move event per asset per 15-minute window.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=15)
    dedup_window = now - timedelta(minutes=16)  # slightly wider for query safety

    assets = db.query(Asset).filter(Asset.is_active == True).all()

    for asset in assets:
        # Latest price
        latest = (
            db.query(Price)
            .filter(Price.asset_id == asset.id, Price.timestamp >= window_start)
            .order_by(Price.timestamp.desc())
            .first()
        )
        if latest is None:
            continue

        # Price from ~15 min ago
        prev = (
            db.query(Price)
            .filter(
                Price.asset_id == asset.id,
                Price.timestamp < window_start,
                Price.timestamp >= window_start - timedelta(minutes=15),
            )
            .order_by(Price.timestamp.desc())
            .first()
        )
        if prev is None or prev.close == 0:
            continue

        change_pct = ((latest.close - prev.close) / prev.close) * 100
        if abs(change_pct) < PRICE_MOVE_THRESHOLD_PCT:
            continue

        direction = "up" if change_pct > 0 else "down"
        sign = "+" if change_pct > 0 else ""
        importance = min(10.0, abs(change_pct))

        title = f"{asset.symbol} {sign}{change_pct:.1f}% — {asset.name}"
        body = (
            f"{asset.name} ({asset.symbol}) moved {sign}{change_pct:.2f}% "
            f"in the last 15 minutes, trading at {latest.close:,.4f} {asset.currency}."
        )
        subtype = asset.asset_type.value  # stock, crypto, commodity, fx

        # Upsert: one event per asset per 15-min window (identified by dedup_window)
        _upsert_feed_event(
            db,
            event_type="price_move",
            event_subtype=subtype,
            title=title,
            body=body,
            published_at=now,
            related_asset_ids=[asset.id],
            related_country_ids=[asset.country_id] if asset.country_id else [],
            importance_score=importance,
            event_data={
                "symbol": asset.symbol,
                "change_pct": round(change_pct, 4),
                "price": latest.close,
                "currency": asset.currency,
                "direction": direction,
            },
        )


# ── Macro release events ───────────────────────────────────────────────────────

def _generate_macro_releases(db) -> None:
    """
    Look for new economic indicator rows inserted in the last 24 hours.
    Create a feed event per unique (country, indicator) pair found.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    # CountryIndicator doesn't have created_at, so we use period_date as a proxy
    # (new rows added by seeders will have recent period_dates for real releases).
    # In production, add a created_at column to country_indicators via migration.
    # For now, surface rows where period_date is within the last 30 days.
    from app.models.country import Country

    recent = (
        db.query(CountryIndicator, Country)
        .join(Country, Country.id == CountryIndicator.country_id)
        .filter(
            CountryIndicator.period_date >= (now - timedelta(days=30)).date()
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(50)  # cap to avoid flooding the feed
        .all()
    )

    for indicator_row, country in recent:
        importance = INDICATOR_IMPORTANCE.get(
            indicator_row.indicator, DEFAULT_INDICATOR_IMPORTANCE
        )
        label = indicator_row.indicator.replace("_", " ").title()
        value_str = f"{indicator_row.value:,.2f}"
        published_at = datetime.combine(
            indicator_row.period_date, datetime.min.time()
        ).replace(tzinfo=timezone.utc)

        title = f"{country.flag_emoji or ''} {country.name}: {label} {value_str}"
        body = (
            f"{country.name}'s {label} stands at {value_str} "
            f"as of {indicator_row.period_date.strftime('%B %Y')}. "
            f"Source: {indicator_row.source}."
        )

        _upsert_feed_event(
            db,
            event_type="macro_release",
            event_subtype=indicator_row.indicator,
            title=title,
            body=body,
            published_at=published_at,
            related_asset_ids=[],
            related_country_ids=[country.id],
            importance_score=importance,
            event_data={
                "country_code": country.code,
                "indicator": indicator_row.indicator,
                "value": indicator_row.value,
                "period": str(indicator_row.period_date),
                "source": indicator_row.source,
            },
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_feed_event(
    db,
    event_type: str,
    event_subtype: str,
    title: str,
    body: str,
    published_at: datetime,
    related_asset_ids: list[int],
    related_country_ids: list[int],
    importance_score: float,
    event_data: dict,
) -> None:
    """
    Insert a feed event; skip silently if an equivalent event already exists
    within the last 15 minutes (prevents flooding on repeated task runs).
    """
    dedup_cutoff = published_at - timedelta(minutes=15)
    exists = (
        db.query(FeedEvent.id)
        .filter(
            FeedEvent.event_type == event_type,
            FeedEvent.event_subtype == event_subtype,
            FeedEvent.published_at >= dedup_cutoff,
            # Check if same asset set to avoid duplicate price_move cards
            FeedEvent.related_asset_ids == related_asset_ids,
        )
        .first()
    )
    if exists:
        return

    event = FeedEvent(
        title=title,
        body=body,
        event_type=event_type,
        event_subtype=event_subtype,
        published_at=published_at,
        related_asset_ids=related_asset_ids or None,
        related_country_ids=related_country_ids or None,
        importance_score=importance_score,
        event_data=event_data,
    )
    db.add(event)
