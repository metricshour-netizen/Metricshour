"""
Feed event seeder — generates initial FeedEvents from existing DB data.

Idempotent: skips events that already exist (matched by title + day).

Sources:
  price_moves       — assets where price moved >3% between last two daily candles
  indicator_release — recent GDP, inflation, interest_rate rows per country
  trade_summaries   — G20 bilateral trade pairs with notable values
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetType, Price
from app.models.country import Country, CountryIndicator, TradePair
from app.models.feed import FeedEvent

log = logging.getLogger(__name__)

# Indicators we surface in the feed (highest-impact ones only for the seed)
SEED_INDICATORS = {
    "real_interest_rate_pct": 10.0,
    "gdp_growth_pct":         9.0,
    "inflation_pct":          9.0,
    "unemployment_pct":       8.0,
    "government_debt_gdp_pct": 7.0,
    "current_account_gdp_pct": 6.0,
}


def seed_feed(db: Session) -> None:
    total = 0
    total += _seed_price_moves(db)
    total += _seed_indicator_releases(db)
    total += _seed_trade_summaries(db)
    db.commit()
    log.info("feed seeder: inserted %d events", total)


# ── Price moves ───────────────────────────────────────────────────────────────

def _seed_price_moves(db: Session) -> int:
    """
    Find assets where the most recent daily price moved >3% vs the previous day.
    """
    count = 0
    assets = db.query(Asset).filter(Asset.is_active == True).all()

    for asset in assets:
        prices = (
            db.query(Price)
            .filter(Price.asset_id == asset.id, Price.interval == "1d")
            .order_by(Price.timestamp.desc())
            .limit(2)
            .all()
        )
        if len(prices) < 2:
            continue

        latest, prev = prices[0], prices[1]
        if prev.close == 0:
            continue

        change_pct = ((latest.close - prev.close) / prev.close) * 100
        if abs(change_pct) < 3.0:
            continue

        sign = "+" if change_pct > 0 else ""
        importance = min(10.0, abs(change_pct))
        title = f"{asset.symbol} {sign}{change_pct:.1f}% — {asset.name}"

        if _event_exists(db, title):
            continue

        body = (
            f"{asset.name} ({asset.symbol}) moved {sign}{change_pct:.2f}% "
            f"on the last trading day, closing at {latest.close:,.4f} {asset.currency}."
        )

        db.add(FeedEvent(
            title=title,
            body=body,
            event_type="price_move",
            event_subtype=asset.asset_type.value,
            published_at=latest.timestamp.replace(tzinfo=timezone.utc)
            if latest.timestamp.tzinfo is None else latest.timestamp,
            related_asset_ids=[asset.id],
            related_country_ids=[asset.country_id] if asset.country_id else None,
            importance_score=importance,
            event_data={
                "symbol": asset.symbol,
                "change_pct": round(change_pct, 4),
                "price": latest.close,
                "currency": asset.currency,
                "direction": "up" if change_pct > 0 else "down",
            },
        ))
        count += 1

    log.info("feed seeder: %d price_move events", count)
    return count


# ── Indicator releases ────────────────────────────────────────────────────────

def _seed_indicator_releases(db: Session) -> int:
    """Surface the most recent value for each key indicator per country."""
    count = 0
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=365 * 3)

    rows = (
        db.query(CountryIndicator, Country)
        .join(Country, Country.id == CountryIndicator.country_id)
        .filter(
            CountryIndicator.indicator.in_(list(SEED_INDICATORS.keys())),
            CountryIndicator.period_date >= cutoff,
        )
        .order_by(CountryIndicator.period_date.desc())
        .all()
    )

    seen: set[tuple] = set()  # (country_id, indicator) — one card per pair

    for indicator_row, country in rows:
        key = (country.id, indicator_row.indicator)
        if key in seen:
            continue
        seen.add(key)

        importance = SEED_INDICATORS.get(indicator_row.indicator, 5.0)
        label = indicator_row.indicator.replace("_", " ").title()
        value_str = f"{indicator_row.value:,.2f}"
        flag = country.flag_emoji or ""

        title = f"{flag} {country.name}: {label} {value_str}"
        if _event_exists(db, title):
            continue

        published_at = datetime.combine(
            indicator_row.period_date, datetime.min.time()
        ).replace(tzinfo=timezone.utc)

        body = (
            f"{country.name}'s {label} stands at {value_str} "
            f"as of {indicator_row.period_date.strftime('%B %Y')}. "
            f"Source: {indicator_row.source}."
        )

        db.add(FeedEvent(
            title=title,
            body=body,
            event_type="indicator_release",
            event_subtype=indicator_row.indicator,
            published_at=published_at,
            related_asset_ids=None,
            related_country_ids=[country.id],
            importance_score=importance,
            event_data={
                "country_code": country.code,
                "indicator": indicator_row.indicator,
                "value": indicator_row.value,
                "period": str(indicator_row.period_date),
                "source": indicator_row.source,
            },
        ))
        count += 1

    log.info("feed seeder: %d indicator_release events", count)
    return count


# ── Trade summaries ───────────────────────────────────────────────────────────

def _seed_trade_summaries(db: Session) -> int:
    """Create one trade_update card per G20 trade pair with value > $10B."""
    count = 0

    pairs = (
        db.query(TradePair, Country, Country)
        .join(Country, Country.id == TradePair.exporter_id, isouter=False)
        .limit(200)
        .all()
    )

    # Simpler query — just get top pairs by value
    from sqlalchemy import desc
    pair_rows = (
        db.query(TradePair)
        .filter(TradePair.trade_value_usd >= 10_000_000_000)
        .order_by(desc(TradePair.trade_value_usd))
        .limit(40)
        .all()
    )

    country_cache: dict[int, Country] = {}

    def get_country(cid: int) -> Country | None:
        if cid not in country_cache:
            country_cache[cid] = db.get(Country, cid)
        return country_cache[cid]

    for pair in pair_rows:
        exp = get_country(pair.exporter_id)
        imp = get_country(pair.importer_id)
        if not exp or not imp:
            continue

        value_b = pair.trade_value_usd / 1e9
        title = (
            f"{exp.flag_emoji or exp.code}→{imp.flag_emoji or imp.code} "
            f"Trade: ${value_b:.0f}B ({pair.year})"
        )
        if _event_exists(db, title):
            continue

        body = (
            f"{exp.name} exported ${value_b:.1f}B to {imp.name} in {pair.year}. "
        )
        if pair.top_export_products:
            top = pair.top_export_products[:3] if isinstance(pair.top_export_products, list) else []
            names = [p.get("name", str(p)) for p in top if isinstance(p, dict)]
            if names:
                body += f"Top exports: {', '.join(names)}."

        published_at = datetime(pair.year, 7, 1, tzinfo=timezone.utc)

        db.add(FeedEvent(
            title=title,
            body=body,
            event_type="trade_update",
            event_subtype="bilateral",
            published_at=published_at,
            related_asset_ids=None,
            related_country_ids=[pair.exporter_id, pair.importer_id],
            importance_score=4.0,
            event_data={
                "exporter": exp.code,
                "importer": imp.code,
                "value_usd": pair.trade_value_usd,
                "year": pair.year,
            },
        ))
        count += 1

    log.info("feed seeder: %d trade_update events", count)
    return count


# ── Helpers ───────────────────────────────────────────────────────────────────

def _event_exists(db: Session, title: str) -> bool:
    """Check if an event with this exact title already exists."""
    return db.query(FeedEvent.id).filter(FeedEvent.title == title).first() is not None
