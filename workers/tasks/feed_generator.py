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
from tasks.summaries import _call_ai

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

# Price-move thresholds by asset type — lower = more events
PRICE_MOVE_THRESHOLD: dict[str, float] = {
    "crypto":    0.8,   # crypto: 0.8% triggers a card (active 24/7 market)
    "stock":     0.8,   # stocks: 0.8% intraday move is worth surfacing
    "commodity": 0.6,   # commodities: 0.6% signals direction change
    "fx":        0.2,   # FX: 0.2% is significant for major pairs
    "index":     0.5,   # indices: 0.5% is meaningful
    "etf":       0.8,
    "bond":      0.15,  # bond prices: 0.15% matters for fixed income
}

# Hard ceiling — moves above these are almost certainly bad source data ticks.
# Second line of defence after ingestion-level spike guards.
PRICE_MOVE_MAX_PCT: dict[str, float] = {
    "crypto":    40.0,
    "stock":     14.0,
    "commodity": 11.0,
    "fx":        3.0,
    "index":     8.0,
    "etf":       14.0,
    "bond":      5.0,
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


# ── AI body generation ────────────────────────────────────────────────────────

def _ai_price_body(asset_name: str, symbol: str, change_pct: float, price: float,
                   currency: str, asset_type: str) -> str | None:
    """Generate a 2-sentence analyst take on a price move. DeepSeek-first (bulk speed)."""
    sign = "+" if change_pct > 0 else ""
    direction = "surged" if change_pct > 0 else "dropped"
    prompt = (
        f"Write exactly 2 sentences (30-45 words total) on this market event: "
        f"{asset_name} ({symbol}) {direction} {sign}{change_pct:.2f}% in the last 15 minutes, "
        f"now trading at {price:,.4f} {currency}. Asset class: {asset_type}. "
        f"Sentence 1: state the move and current price. "
        f"Sentence 2: give one concrete market context or implication (use a real data point or ratio). "
        f"No filler. No hedging. Active voice."
    )
    return _call_ai(prompt, min_words=25, max_words=50, prefer_gemini=False)


def _ai_macro_body(country_name: str, indicator_label: str, value_str: str,
                   period: str, source: str, importance: float) -> str | None:
    """Generate a 2-sentence macro data take. Gemini for high-importance (>=8), DeepSeek otherwise."""
    prompt = (
        f"Write exactly 2 sentences (35-50 words total) on this economic data release: "
        f"{country_name} {indicator_label} = {value_str} as of {period} (source: {source}). "
        f"Sentence 1: state the figure and what it measures. "
        f"Sentence 2: give one direct market or policy implication using a specific number. "
        f"No filler. Assert, do not hedge. Active voice."
    )
    return _call_ai(prompt, min_words=28, max_words=55, prefer_gemini=(importance >= 8))


# ── Price move events ─────────────────────────────────────────────────────────

def _generate_price_moves(db) -> list[tuple[str, str]]:
    """
    Compare the latest price to the price 15 minutes earlier.
    If abs(change_pct) >= threshold, create/update a feed event.
    De-duplicate: one price_move event per asset per 15-minute window.
    Returns list of (entity_type, entity_code) tuples for significant events.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=5)   # compare last 5-min price

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
        max_pct = PRICE_MOVE_MAX_PCT.get(asset.asset_type.value, 20.0)
        if abs(change_pct) < threshold:
            continue
        if abs(change_pct) > max_pct:
            log.warning(
                'feed_generator: spike ignored %s %.1f%% (max %.1f%%)',
                asset.symbol, change_pct, max_pct,
            )
            continue

        direction = "up" if change_pct > 0 else "down"
        sign = "+" if change_pct > 0 else ""
        importance = min(10.0, abs(change_pct))
        subtype = asset.asset_type.value  # stock, crypto, commodity, fx

        # Dedup check BEFORE calling AI — skip AI if this event would be dropped anyway
        dedup_cutoff = now - timedelta(minutes=5)
        already_exists = db.query(FeedEvent.id).filter(
            FeedEvent.event_type == "price_move",
            FeedEvent.event_subtype == subtype,
            FeedEvent.related_asset_ids == [asset.id],
            FeedEvent.published_at >= dedup_cutoff,
        ).first()
        if already_exists:
            continue

        title = f"{asset.symbol} {sign}{change_pct:.1f}% — {asset.name}"
        fallback_body = (
            f"{asset.name} ({asset.symbol}) moved {sign}{change_pct:.2f}% "
            f"in the last 15 minutes, trading at {latest.close:,.4f} {asset.currency}."
        )
        # Only call AI for meaningful moves (≥2%) — use template for small noise moves
        if abs(change_pct) >= 2.0:
            body = (
                _ai_price_body(asset.name, asset.symbol, change_pct, latest.close,
                               asset.currency, asset.asset_type.value)
                or fallback_body
            )
        else:
            body = fallback_body

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
            CountryIndicator.period_date >= (now - timedelta(days=1095)).date(),  # 3 years back
            Country.code.in_(G20_CODES),
        )
        .order_by(CountryIndicator.period_date.desc(), CountryIndicator.country_id)
        .limit(100)
        .all()
    )

    for indicator_row, country in recent:
        importance = INDICATOR_IMPORTANCE.get(indicator_row.indicator, DEFAULT_INDICATOR_IMPORTANCE)
        label = indicator_row.indicator.replace("_", " ").title()
        value_str = f"{indicator_row.value:,.2f}"

        title = f"{country.flag_emoji or ''} {country.name}: {label} {value_str}"
        period_str = indicator_row.period_date.strftime("%B %Y")
        fallback_body = (
            f"{country.name}'s {label} stands at {value_str} "
            f"as of {period_str}. "
            f"Source: {indicator_row.source}."
        )
        # Only call AI for high-importance macro events (≥7) — template is fine for tier-2
        if importance >= 7.0:
            body = (
                _ai_macro_body(country.name, label, value_str, period_str,
                               indicator_row.source, importance)
                or fallback_body
            )
        else:
            body = fallback_body

        # Dedup per (country, indicator, period) — not just indicator.
        # Each data point published once; only re-published if period_date is new.
        period_slug = indicator_row.period_date.strftime("%Y-%m")
        subtype_with_period = f"{indicator_row.indicator}:{period_slug}"

        _upsert_feed_event(
            db,
            event_type="macro_release",
            event_subtype=subtype_with_period,
            title=title,
            body=body,
            published_at=now,
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
        dedup_minutes = 5    # one card per asset per 5 min — high-frequency feed
    else:
        # macro/indicator: one card per (country, indicator, period) — never re-publish.
        # subtype encodes the period (e.g. "gdp_growth_pct:2024-01") so the same
        # data point is permanent. 1-year window handles any edge-case clock skew.
        dedup_minutes = 525960  # 1 year

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
