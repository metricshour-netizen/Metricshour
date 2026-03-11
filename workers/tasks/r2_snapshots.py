"""
R2 JSON snapshot writer — MetricsHour data CDN.

Writes processed JSON to Cloudflare R2 daily so pages can be served
from the edge without hitting FastAPI or Postgres.

R2 key layout:
  snapshots/countries/{slug}.json          — full country overview
  snapshots/stocks/{ticker}.json           — stock detail + geo revenues
  snapshots/trade/{exp}-{imp}.json         — bilateral trade pair
  snapshots/lists/countries.json           — full country list
  snapshots/lists/assets.json              — asset list (stocks + crypto + commodities)
  snapshots/rankings/stability.json        — country stability scores
  snapshots/meta/snapshot_index.json       — manifest of all generated keys + timestamps

Run manually:
  celery -A celery_app call tasks.r2_snapshots.write_r2_snapshots
"""

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, func, or_

# Make backend importable (workers/ sits one level above backend/app/)
import sys, os
sys.path.insert(0, '/root/metricshour/backend')

from app.database import SessionLocal
from app.models import Country, Asset, AssetType, Price, StockCountryRevenue, TradePair
from app.models.country import CountryIndicator
from app.storage import get_r2_client
from app.config import settings

log = logging.getLogger(__name__)

_BUCKET = None  # resolved lazily


def _bucket() -> str:
    return settings.r2_bucket_name


def _upload(key: str, data: dict | list) -> None:
    body = json.dumps(data, default=str).encode()
    get_r2_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=body,
        ContentType="application/json",
        # s-maxage = Cloudflare edge TTL; max-age = browser TTL
        CacheControl="public, s-maxage=3600, max-age=3600, stale-while-revalidate=86400",
    )


def _purge_cf_cache(urls: list[str]) -> None:
    token = getattr(settings, "cf_cache_purge_token", None) or os.environ.get("CF_CACHE_PURGE_TOKEN")
    zone_id = getattr(settings, "cf_zone_id", None) or os.environ.get("CF_ZONE_ID")
    if not token or not zone_id:
        log.warning("CF_CACHE_PURGE_TOKEN or CF_ZONE_ID not set — skipping cache purge")
        return
    payload = json.dumps({"files": urls}).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                log.info("CF cache purged: %s", urls)
            else:
                log.warning("CF cache purge failed: %s", result.get("errors"))
    except Exception as exc:
        log.warning("CF cache purge error: %s", exc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _country_summary(c: Country) -> dict:
    groupings = []
    if c.is_g7: groupings.append("G7")
    if c.is_g20: groupings.append("G20")
    if c.is_eu: groupings.append("EU")
    if c.is_eurozone: groupings.append("Eurozone")
    if c.is_nato: groupings.append("NATO")
    if c.is_opec: groupings.append("OPEC")
    if c.is_brics: groupings.append("BRICS")
    if c.is_asean: groupings.append("ASEAN")
    if c.is_oecd: groupings.append("OECD")
    if c.is_commonwealth: groupings.append("Commonwealth")
    return {
        "id": c.id,
        "code": c.code,
        "code3": c.code3,
        "name": c.name,
        "name_official": c.name_official,
        "capital": c.capital_city,
        "flag": c.flag_emoji,
        "slug": c.slug,
        "region": c.region,
        "subregion": c.subregion,
        "currency_code": c.currency_code,
        "currency_symbol": c.currency_symbol,
        "income_level": c.income_level,
        "development_status": c.development_status,
        "is_g7": c.is_g7,
        "is_g20": c.is_g20,
        "is_eu": c.is_eu,
        "is_nato": c.is_nato,
        "is_opec": c.is_opec,
        "is_brics": c.is_brics,
        "credit_rating_sp": c.credit_rating_sp,
        "credit_rating_moodys": c.credit_rating_moodys,
        "major_exports": c.major_exports,
        "natural_resources": c.natural_resources,
        "groupings": groupings,
    }


def _asset_summary(a: Asset, country: Country | None = None, price: Price | None = None) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "name": a.name,
        "asset_type": a.asset_type.value if a.asset_type else None,
        "exchange": a.exchange,
        "currency": a.currency,
        "sector": a.sector,
        "industry": a.industry,
        "market_cap_usd": a.market_cap_usd,
        "base_currency": a.base_currency,
        "quote_currency": a.quote_currency,
        "country": {
            "code": country.code,
            "name": country.name,
            "flag": country.flag_emoji,
        } if country else None,
        "price": {
            "close": price.close,
            "open": price.open,
            "high": price.high,
            "low": price.low,
            "timestamp": price.timestamp.isoformat(),
        } if price else None,
    }


# ── Snapshot writers ────────────────────────────────────────────────────────────

def _write_country_list(db) -> int:
    countries = db.execute(select(Country).order_by(Country.name)).scalars().all()
    data = [_country_summary(c) for c in countries]
    _upload("snapshots/lists/countries.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(data),
        "data": data,
    })
    return len(data)


def _write_asset_list(db) -> int:
    assets = db.execute(
        select(Asset).where(Asset.is_active == True).order_by(Asset.market_cap_usd.desc().nullslast())
    ).scalars().all()

    country_ids = {a.country_id for a in assets if a.country_id}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    asset_ids = [a.id for a in assets]
    prices: dict[int, Price] = {}
    if asset_ids:
        latest_sq = (
            select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
            .where(Price.asset_id.in_(asset_ids))
            .group_by(Price.asset_id)
            .subquery()
        )
        price_rows = db.execute(
            select(Price).join(
                latest_sq,
                (Price.asset_id == latest_sq.c.asset_id) &
                (Price.timestamp == latest_sq.c.max_ts),
            )
        ).scalars().all()
        prices = {p.asset_id: p for p in price_rows}

    data = [_asset_summary(a, countries.get(a.country_id), prices.get(a.id)) for a in assets]
    _upload("snapshots/lists/assets.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(data),
        "data": data,
    })
    return len(data)


def _write_country_snapshots(db) -> int:
    countries = db.execute(select(Country)).scalars().all()
    written = 0

    for c in countries:
        indicators_rows = db.execute(
            select(CountryIndicator)
            .where(CountryIndicator.country_id == c.id)
            .order_by(CountryIndicator.indicator, CountryIndicator.period_date.desc())
        ).scalars().all()

        latest: dict[str, float] = {}
        latest_years: dict[str, int] = {}
        for row in indicators_rows:
            if row.indicator not in latest:
                latest[row.indicator] = row.value
                latest_years[row.indicator] = row.period_date.year

        # Trade partners
        trade_pairs = db.execute(
            select(TradePair)
            .where(or_(TradePair.exporter_id == c.id, TradePair.importer_id == c.id))
            .order_by(TradePair.trade_value_usd.desc())
            .limit(20)
        ).scalars().all()
        partner_ids = {(p.importer_id if p.exporter_id == c.id else p.exporter_id) for p in trade_pairs}
        partner_countries: dict[int, Country] = {}
        if partner_ids:
            rows = db.execute(select(Country).where(Country.id.in_(partner_ids))).scalars().all()
            partner_countries = {pc.id: pc for pc in rows}
        trade_partners = []
        seen_partners: set[str] = set()
        for p in trade_pairs:
            is_exp = p.exporter_id == c.id
            pid = p.importer_id if is_exp else p.exporter_id
            pc = partner_countries.get(pid)
            if not pc or pc.code in seen_partners:
                continue
            seen_partners.add(pc.code)
            exports = p.exports_usd if is_exp else p.imports_usd
            imports = p.imports_usd if is_exp else p.exports_usd
            trade_partners.append({
                "partner": {"code": pc.code, "name": pc.name, "flag": pc.flag_emoji},
                "exports_usd": exports,
                "imports_usd": imports,
                "balance_usd": (exports or 0) - (imports or 0),
                "trade_value_usd": p.trade_value_usd,
            })

        # Stocks with revenue from this country
        rev_rows = db.execute(
            select(StockCountryRevenue, Asset)
            .join(Asset, StockCountryRevenue.asset_id == Asset.id)
            .where(StockCountryRevenue.country_id == c.id)
            .order_by(StockCountryRevenue.fiscal_year.desc(), StockCountryRevenue.revenue_pct.desc())
        ).all()
        seen_assets: set[int] = set()
        exposed_stocks = []
        for rev, asset in rev_rows:
            if asset.id not in seen_assets:
                seen_assets.add(asset.id)
                exposed_stocks.append({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "sector": asset.sector,
                    "market_cap_usd": asset.market_cap_usd,
                    "revenue_pct": rev.revenue_pct,
                    "fiscal_year": rev.fiscal_year,
                })

        # Stocks headquartered in this country
        local_stock_rows = db.execute(
            select(Asset)
            .where(Asset.country_id == c.id, Asset.asset_type == AssetType.stock, Asset.is_active == True)
            .order_by(Asset.market_cap_usd.desc().nullslast())
            .limit(20)
        ).scalars().all()
        local_stocks = [{"symbol": a.symbol, "name": a.name, "sector": a.sector, "market_cap_usd": a.market_cap_usd} for a in local_stock_rows]

        data = {
            **_country_summary(c),
            "indicators": latest,
            "indicator_years": latest_years,
            "trade_partners": trade_partners,
            "exposed_stocks": exposed_stocks,
            "local_stocks": local_stocks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _upload(f"snapshots/countries/{c.slug}.json", data)
        written += 1

    return written


def _write_stock_snapshots(db) -> int:
    stocks = db.execute(
        select(Asset).where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
    ).scalars().all()

    written = 0
    for a in stocks:
        # Latest price
        price = db.execute(
            select(Price)
            .where(Price.asset_id == a.id)
            .order_by(Price.timestamp.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Geographic revenue
        rev_rows = db.execute(
            select(StockCountryRevenue, Country)
            .join(Country, StockCountryRevenue.country_id == Country.id)
            .where(StockCountryRevenue.asset_id == a.id)
            .order_by(StockCountryRevenue.fiscal_year.desc(), StockCountryRevenue.revenue_pct.desc())
        ).all()

        country_revenues = []
        seen_countries: set[int] = set()
        for rev, country in rev_rows:
            if country.id not in seen_countries:
                seen_countries.add(country.id)
                country_revenues.append({
                    "country": {
                        "code": country.code,
                        "name": country.name,
                        "flag": country.flag_emoji,
                    },
                    "revenue_pct": rev.revenue_pct,
                    "revenue_usd": rev.revenue_usd,
                    "fiscal_year": rev.fiscal_year,
                })

        hq_country = None
        if a.country_id:
            hq_country = db.execute(select(Country).where(Country.id == a.country_id)).scalar_one_or_none()

        data = {
            **_asset_summary(a, hq_country, price),
            "country_revenues": country_revenues,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _upload(f"snapshots/stocks/{a.symbol.lower()}.json", data)
        written += 1

    return written


def _write_trade_snapshots(db) -> int:
    # Latest year per pair
    latest_sq = (
        select(
            TradePair.exporter_id,
            TradePair.importer_id,
            func.max(TradePair.year).label("max_year"),
        )
        .group_by(TradePair.exporter_id, TradePair.importer_id)
        .subquery()
    )
    pairs = db.execute(
        select(TradePair).join(
            latest_sq,
            (TradePair.exporter_id == latest_sq.c.exporter_id)
            & (TradePair.importer_id == latest_sq.c.importer_id)
            & (TradePair.year == latest_sq.c.max_year),
        )
    ).scalars().all()

    country_ids = {p.exporter_id for p in pairs} | {p.importer_id for p in pairs}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    # Fetch latest macro indicators for all countries involved
    MACRO_KEYS = ["gdp_usd", "gdp_growth_pct", "inflation_pct", "gdp_per_capita_usd", "unemployment_pct", "interest_rate_pct"]
    ind_rows = db.execute(
        select(CountryIndicator)
        .where(
            CountryIndicator.country_id.in_(country_ids),
            CountryIndicator.indicator.in_(MACRO_KEYS),
        )
        .order_by(CountryIndicator.country_id, CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()

    # latest value per (country_id, indicator)
    country_indicators: dict[int, dict[str, float]] = {}
    for row in ind_rows:
        cid = row.country_id
        if cid not in country_indicators:
            country_indicators[cid] = {}
        if row.indicator not in country_indicators[cid]:
            country_indicators[cid][row.indicator] = row.value

    written = 0
    for p in pairs:
        exp = countries.get(p.exporter_id)
        imp = countries.get(p.importer_id)
        if not exp or not imp:
            continue

        exp_ind = country_indicators.get(p.exporter_id, {})
        imp_ind = country_indicators.get(p.importer_id, {})

        trade_data = {
            "id": p.id,
            "year": p.year,
            "data_source": p.data_source,
            "exporter": {"code": exp.code, "name": exp.name, "flag": exp.flag_emoji},
            "importer": {"code": imp.code, "name": imp.name, "flag": imp.flag_emoji},
            "trade_value_usd": p.trade_value_usd,
            "exports_usd": p.exports_usd,
            "imports_usd": p.imports_usd,
            "balance_usd": p.balance_usd,
            "exporter_gdp_share_pct": p.exporter_gdp_share_pct,
            "importer_gdp_share_pct": p.importer_gdp_share_pct,
            "top_export_products": p.top_export_products or [],
            "top_import_products": p.top_import_products or [],
        }

        key = f"snapshots/trade/{exp.slug}--{imp.slug}.json"
        data = {
            "exporter": {"code": exp.code, "name": exp.name, "flag": exp.flag_emoji, "currency_code": exp.currency_code, "indicators": exp_ind},
            "importer": {"code": imp.code, "name": imp.name, "flag": imp.flag_emoji, "currency_code": imp.currency_code, "indicators": imp_ind},
            "trade_data": trade_data,
            "canonical_pair": f"{exp.slug}--{imp.slug}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _upload(key, data)
        written += 1

    return written


def _write_stability_rankings(db) -> int:
    """Country stability scores — composite of governance WGI indicators."""
    WGI = [
        "rule_of_law_index", "political_stability_index", "government_effectiveness_index",
        "regulatory_quality_index", "voice_accountability_index", "control_of_corruption_index",
    ]

    countries = db.execute(select(Country).order_by(Country.name)).scalars().all()
    country_ids = [c.id for c in countries]

    # Latest value per (country, indicator)
    rows = db.execute(
        select(CountryIndicator)
        .where(
            CountryIndicator.country_id.in_(country_ids),
            CountryIndicator.indicator.in_(WGI),
        )
        .order_by(CountryIndicator.country_id, CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()

    scores: dict[int, dict[str, float]] = {}
    seen: set[tuple[int, str]] = set()
    for row in rows:
        k = (row.country_id, row.indicator)
        if k not in seen:
            seen.add(k)
            scores.setdefault(row.country_id, {})[row.indicator] = row.value

    rankings = []
    country_map = {c.id: c for c in countries}
    for cid, ind_scores in scores.items():
        if len(ind_scores) < 3:  # skip countries with sparse governance data
            continue
        composite = sum(ind_scores.values()) / len(ind_scores)
        c = country_map[cid]
        rankings.append({
            "code": c.code,
            "name": c.name,
            "flag": c.flag_emoji,
            "composite_score": round(composite, 4),
            "components": {k: round(v, 4) for k, v in ind_scores.items()},
        })

    rankings.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    _upload("snapshots/rankings/stability.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rankings),
        "data": rankings,
    })
    return len(rankings)


# ── Main task ─────────────────────────────────────────────────────────────────

@shared_task(name="tasks.r2_snapshots.write_r2_snapshots", bind=True, max_retries=2, default_retry_delay=300)
def write_r2_snapshots(self):
    """Write all processed JSON snapshots to Cloudflare R2."""
    if not (settings.r2_endpoint and settings.r2_access_key_id and settings.r2_secret_access_key):
        log.warning("R2 credentials not configured — skipping snapshot write")
        return {"status": "skipped", "reason": "R2 not configured"}

    t0 = time.time()
    stats: dict[str, int] = {}

    try:
        with SessionLocal() as db:
            log.info("R2 snapshots: writing country list…")
            stats["country_list"] = _write_country_list(db)

            log.info("R2 snapshots: writing asset list…")
            stats["asset_list"] = _write_asset_list(db)

            log.info("R2 snapshots: writing %d country snapshots…", stats["country_list"])
            stats["countries"] = _write_country_snapshots(db)

            log.info("R2 snapshots: writing stock snapshots…")
            stats["stocks"] = _write_stock_snapshots(db)

            log.info("R2 snapshots: writing trade pair snapshots…")
            stats["trade_pairs"] = _write_trade_snapshots(db)

            log.info("R2 snapshots: writing stability rankings…")
            stats["rankings"] = _write_stability_rankings(db)

        # Write manifest
        elapsed = round(time.time() - t0, 1)
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "counts": stats,
        }
        _upload("snapshots/meta/snapshot_index.json", manifest)

        total = sum(stats.values())
        log.info("R2 snapshots complete: %d objects in %.1fs", total, elapsed)

        # Purge list snapshots + all country/stock/trade detail pages from CF cache
        base = "https://cdn.metricshour.com"
        purge_urls = [
            f"{base}/snapshots/lists/countries.json",
            f"{base}/snapshots/lists/assets.json",
        ]
        with SessionLocal() as db2:
            slugs = [r[0] for r in db2.execute(select(Country.slug)).all()]
            purge_urls += [f"{base}/snapshots/countries/{s}.json" for s in slugs]

        for i in range(0, len(purge_urls), 30):
            _purge_cf_cache(purge_urls[i:i + 30])

        return {"status": "ok", "elapsed_seconds": elapsed, **stats}

    except Exception as exc:
        log.exception("R2 snapshot write failed: %s", exc)
        raise self.retry(exc=exc)
