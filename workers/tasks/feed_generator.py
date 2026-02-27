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

# ── Indicator importance weights (0–10) — matched to actual DB column names ───
INDICATOR_IMPORTANCE: dict[str, float] = {
    # World Bank / custom names
    "gdp_growth_pct":               9.0,
    "inflation_pct":                9.0,
    "unemployment_pct":             8.0,
    "current_account_gdp_pct":      7.0,
    "government_debt_gdp_pct":      7.0,
    "budget_balance_gdp_pct":       6.0,
    "trade_balance_gdp_pct":        6.0,
    "foreign_reserves_usd":         5.0,
    "fdi_inflows_usd":              5.0,
    "consumer_confidence":          4.0,
    "eur_fx_rate":                  6.0,
    # IMF names (only non-forecast rows, period_date <= today enforced in query)
    "imf_gdp_growth_pct":           9.0,
    "imf_inflation_pct":            9.0,
    "imf_unemployment_pct":         8.0,
    "imf_fiscal_balance_pct_gdp":   7.0,
    "imf_current_account_pct_gdp":  7.0,
    "imf_govt_gross_debt_pct_gdp":  6.0,
}
DEFAULT_INDICATOR_IMPORTANCE = 3.0

# Price-move thresholds by asset type (crypto moves more, stocks less)
PRICE_MOVE_THRESHOLD: dict[str, float] = {
    "crypto":    1.5,   # crypto moves fast — 1.5% is meaningful
    "stock":     1.5,   # stocks: notable intraday move
    "commodity": 1.2,   # commodities: 1.2% signals direction
    "fx":        0.4,   # FX: 0.4% is a big move for major pairs
    "index":     1.0,   # indices: 1% is significant
    "etf":       1.5,
    "bond":      0.3,   # bond prices rarely move much
}


@app.task(name='tasks.feed_generator.generate_feed_events', bind=True, max_retries=2)
def generate_feed_events(self):
    db = SessionLocal()
    try:
        triggered = _generate_price_moves(db)
        triggered += _generate_macro_releases(db)
        db.commit()
        log.info("feed_generator: completed — %d events triggered summary refreshes", len(triggered))
        # Async summary refresh for significant events (importance >= 7)
        for entity_type, entity_code in triggered:
            from tasks.summaries import refresh_entity_summary
            refresh_entity_summary.delay(entity_type, entity_code)
    except Exception as exc:
        db.rollback()
        log.error("feed_generator: failed — %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


# ── Price move events ─────────────────────────────────────────────────────────

def _generate_price_moves(db) -> list[tuple[str, str]]:
    """
    Compare the latest price to the price 15 minutes earlier.
    If abs(change_pct) >= threshold, create/update a feed event.
    De-duplicate: one price_move event per asset per 15-minute window.
    Returns list of (entity_type, entity_code) tuples for significant events.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=15)
    dedup_window = now - timedelta(minutes=16)  # slightly wider for query safety

    assets = db.query(Asset).filter(Asset.is_active == True).all()
    triggered: list[tuple[str, str]] = []

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
        threshold = PRICE_MOVE_THRESHOLD.get(asset.asset_type.value, 1.5)
        if abs(change_pct) < threshold:
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
        # Trigger summary refresh for large moves (≥7% = high importance)
        if importance >= 7 and asset.asset_type.value == "stock":
            triggered.append(("stock", asset.symbol))

    return triggered


# ── Macro release events ───────────────────────────────────────────────────────

def _generate_macro_releases(db) -> list[tuple[str, str]]:
    """
    Surface high-importance economic indicator data as feed events.
    Uses NOW as published_at (when we surface it) not period_date.
    Skips future-dated forecasts (period_date > today).
    Only emits high-importance indicators to avoid flooding the feed.
    """
    from app.models.country import Country

    now = datetime.now(timezone.utc)
    today = now.date()
    triggered: list[tuple[str, str]] = []

    # Only surface top-tier indicators (importance >= 5)
    high_importance = {k for k, v in INDICATOR_IMPORTANCE.items() if v >= 5.0}

    # G20/major economies only to keep the feed relevant
    G20_CODES = {
        'US', 'CN', 'DE', 'JP', 'GB', 'FR', 'IN', 'BR', 'CA', 'AU',
        'KR', 'IT', 'RU', 'MX', 'SA', 'AR', 'ZA', 'ID', 'TR',
    }

    recent = (
        db.query(CountryIndicator, Country)
        .join(Country, Country.id == CountryIndicator.country_id)
        .filter(
            CountryIndicator.indicator.in_(high_importance),
            CountryIndicator.period_date <= today,          # no forecasts
            CountryIndicator.period_date >= (now - timedelta(days=730)).date(),  # 2 years back
            Country.code.in_(G20_CODES),
        )
        .order_by(CountryIndicator.period_date.desc())
        .limit(30)
        .all()
    )

    for indicator_row, country in recent:
        importance = INDICATOR_IMPORTANCE.get(indicator_row.indicator, DEFAULT_INDICATOR_IMPORTANCE)
        label = indicator_row.indicator.replace("_", " ").title()
        value_str = f"{indicator_row.value:,.2f}"

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
            published_at=now,   # always NOW — not the data period date
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
        # Trigger summary refresh for high-importance macro events
        if importance >= 7:
            triggered.append(("country", country.code))

    return triggered


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
    Insert a feed event. Deduplicates per (type, subtype, asset/country) within
    a rolling window to prevent identical cards on repeated task runs.
    Window: 15 min for price_move, 6 hours for macro/indicator.
    """
    if event_type == 'price_move':
        dedup_minutes = 15
    else:
        # macro/indicator: one card per (country, indicator) per 6 hours
        dedup_minutes = 360

    dedup_cutoff = published_at - timedelta(minutes=dedup_minutes)

    q = db.query(FeedEvent.id).filter(
        FeedEvent.event_type == event_type,
        FeedEvent.event_subtype == event_subtype,
        FeedEvent.published_at >= dedup_cutoff,
    )

    # For price moves: dedup per asset
    if related_asset_ids:
        q = q.filter(FeedEvent.related_asset_ids == related_asset_ids)

    # For macro/indicator: dedup per country
    if related_country_ids:
        q = q.filter(FeedEvent.related_country_ids == related_country_ids)

    if q.first():
        return

    db.add(FeedEvent(
        title=title,
        body=body,
        event_type=event_type,
        event_subtype=event_subtype,
        published_at=published_at,
        related_asset_ids=related_asset_ids or None,
        related_country_ids=related_country_ids or None,
        importance_score=importance_score,
        event_data=event_data,
    ))
