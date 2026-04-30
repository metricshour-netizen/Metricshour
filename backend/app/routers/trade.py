from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, case

from app.database import get_db
from app.limiter import limiter
from app.models import TradePair, Country
from app.models.country import CountryIndicator
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/trade", tags=["trade"])


@router.get("")
@limiter.limit("60/minute")
def list_trade_pairs(
    request: Request,
    exporter: str | None = None,
    importer: str | None = None,
    limit: int = Query(default=3000, ge=1, le=3000),
    db: Session = Depends(get_db),
) -> list[dict]:
    # Subquery: best year per (exporter, importer) pair.
    # Prefer the most recent year that has imports_usd; fall back to max year overall.
    best_year_sq = (
        select(
            TradePair.exporter_id,
            TradePair.importer_id,
            func.coalesce(
                func.max(case((TradePair.imports_usd.isnot(None), TradePair.year), else_=None)),
                func.max(TradePair.year),
            ).label("best_year"),
        )
        .group_by(TradePair.exporter_id, TradePair.importer_id)
        .subquery()
    )

    query = (
        select(TradePair)
        .join(
            best_year_sq,
            (TradePair.exporter_id == best_year_sq.c.exporter_id)
            & (TradePair.importer_id == best_year_sq.c.importer_id)
            & (TradePair.year == best_year_sq.c.best_year),
        )
        .order_by(TradePair.trade_value_usd.desc())
        .limit(limit)
    )

    if exporter:
        exp = db.execute(
            select(Country.id).where(Country.code == exporter.upper())
        ).scalar_one_or_none()
        if exp:
            query = query.where(TradePair.exporter_id == exp)

    if importer:
        imp = db.execute(
            select(Country.id).where(Country.code == importer.upper())
        ).scalar_one_or_none()
        if imp:
            query = query.where(TradePair.importer_id == imp)

    pairs = db.execute(query).scalars().all()

    # Deduplicate: both (A→B) and (B→A) exist in DB — keep only one per relationship.
    # Use min/max of IDs as the canonical key; first hit wins (already ordered by trade value desc).
    seen_pairs: set[tuple[int, int]] = set()
    unique_pairs = []
    for p in pairs:
        key = (min(p.exporter_id, p.importer_id), max(p.exporter_id, p.importer_id))
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique_pairs.append(p)

    # Batch-load countries
    country_ids = {p.exporter_id for p in unique_pairs} | {p.importer_id for p in unique_pairs}
    countries: dict[int, Country] = {}
    if country_ids:
        rows = db.execute(select(Country).where(Country.id.in_(country_ids))).scalars().all()
        countries = {c.id: c for c in rows}

    return [_pair_summary(p, countries) for p in unique_pairs]


@router.get("/{exporter_code}/{importer_code}")
@limiter.limit("120/minute")
def get_trade_pair(
    request: Request,
    exporter_code: str,
    importer_code: str,
    db: Session = Depends(get_db),
) -> dict:
    exp = db.execute(
        select(Country).where(or_(Country.code == exporter_code.upper(), Country.slug == exporter_code.lower()))
    ).scalar_one_or_none()

    imp = db.execute(
        select(Country).where(or_(Country.code == importer_code.upper(), Country.slug == importer_code.lower()))
    ).scalar_one_or_none()

    if not exp or not imp:
        raise HTTPException(status_code=404, detail="Country not found")

    cache_key = f"api:trade:v2:{exp.code}:{imp.code}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Prefer records with both exports+imports populated; fall back to newest year
    _completeness = case((TradePair.imports_usd.isnot(None), 1), else_=0)
    pair = db.execute(
        select(TradePair)
        .where(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
        .order_by(_completeness.desc(), TradePair.year.desc())
        .limit(1)
    ).scalar_one_or_none()

    reversed_pair = False
    if not pair:
        # UN Comtrade stores flows by reporter — try the reverse direction
        _completeness_r = case((TradePair.imports_usd.isnot(None), 1), else_=0)
        pair = db.execute(
            select(TradePair)
            .where(TradePair.exporter_id == imp.id, TradePair.importer_id == exp.id)
            .order_by(_completeness_r.desc(), TradePair.year.desc())
            .limit(1)
        ).scalar_one_or_none()
        if pair:
            reversed_pair = True

    trade_data = None
    if pair:
        if reversed_pair:
            # Re-orient values from exp's perspective (swap exports ↔ imports, negate balance)
            trade_data = {
                "id": pair.id,
                "year": pair.year,
                "data_source": pair.data_source,
                "exporter": _country_ref(exp),
                "importer": _country_ref(imp),
                "trade_value_usd": pair.trade_value_usd,
                "exports_usd": pair.imports_usd,
                "imports_usd": pair.exports_usd,
                "balance_usd": -(pair.balance_usd or 0),
                "exporter_gdp_share_pct": pair.importer_gdp_share_pct,
                "importer_gdp_share_pct": pair.exporter_gdp_share_pct,
                "top_export_products": pair.top_import_products or [],
                "top_import_products": pair.top_export_products or [],
            }
        else:
            countries = {exp.id: exp, imp.id: imp}
            trade_data = _pair_summary(pair, countries)

    # Fetch latest macro indicators for both countries
    indicator_names = ["gdp_usd", "gdp_growth_pct", "inflation_pct"]
    country_ids = [exp.id, imp.id]
    raw_indicators = db.execute(
        select(CountryIndicator)
        .where(
            CountryIndicator.country_id.in_(country_ids),
            CountryIndicator.indicator.in_(indicator_names),
        )
        .order_by(CountryIndicator.country_id, CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()

    # Keep only the most recent value per (country, indicator)
    latest: dict[int, dict[str, float]] = {exp.id: {}, imp.id: {}}
    seen: set[tuple[int, str]] = set()
    for row in raw_indicators:
        key = (row.country_id, row.indicator)
        if key not in seen:
            seen.add(key)
            latest[row.country_id][row.indicator] = row.value

    # canonical_pair = the stored DB direction (used by frontend for canonical tag)
    # When reversed_pair=True, the stored direction is imp→exp, so canonical URL is imp-exp
    if reversed_pair:
        canonical_pair = f"{imp.code.lower()}-{exp.code.lower()}"
    else:
        canonical_pair = f"{exporter_code.lower()}-{importer_code.lower()}"

    result = {
        "exporter": _country_ref(exp, latest.get(exp.id, {})),
        "importer": _country_ref(imp, latest.get(imp.id, {})),
        "trade_data": trade_data,
        "canonical_pair": canonical_pair,
    }
    # Trade data is annual — cache for 6 hours
    cache_set(cache_key, result, ttl_seconds=21600)
    return result


def _pair_summary(pair: TradePair, countries: dict[int, Country]) -> dict:
    exp = countries.get(pair.exporter_id)
    imp = countries.get(pair.importer_id)
    return {
        "id": pair.id,
        "year": pair.year,
        "data_source": pair.data_source,
        "exporter": _country_ref(exp) if exp else None,
        "importer": _country_ref(imp) if imp else None,
        "trade_value_usd": pair.trade_value_usd,
        "exports_usd": pair.exports_usd,
        "imports_usd": pair.imports_usd,
        "balance_usd": pair.balance_usd,
        "exporter_gdp_share_pct": pair.exporter_gdp_share_pct,
        "importer_gdp_share_pct": pair.importer_gdp_share_pct,
        "top_export_products": pair.top_export_products or [],
        "top_import_products": pair.top_import_products or [],
    }


def _country_ref(c: Country, indicators: dict | None = None) -> dict:
    return {
        "code": c.code,
        "slug": c.slug,
        "name": c.name,
        "flag": c.flag_emoji,
        "currency_code": c.currency_code,
        "indicators": indicators or {},
    }


@router.get("/{exporter_code}/{importer_code}/download")
@limiter.limit("20/minute")
def download_trade_data(
    request: Request,
    exporter_code: str,
    importer_code: str,
    db: Session = Depends(get_db),
):
    """Download bilateral trade data as CSV."""
    import csv, io
    from fastapi.responses import StreamingResponse

    exp = db.execute(select(Country).where(Country.code == exporter_code.upper())).scalar_one_or_none()
    imp = db.execute(select(Country).where(Country.code == importer_code.upper())).scalar_one_or_none()
    if not exp or not imp:
        raise HTTPException(status_code=404, detail="Country not found")

    pairs = db.execute(
        select(TradePair).where(TradePair.exporter_id == exp.id, TradePair.importer_id == imp.id)
        .order_by(TradePair.year.desc())
    ).scalars().all()
    if not pairs:
        pairs = db.execute(
            select(TradePair).where(TradePair.exporter_id == imp.id, TradePair.importer_id == exp.id)
            .order_by(TradePair.year.desc())
        ).scalars().all()
    if not pairs:
        raise HTTPException(status_code=404, detail="No trade data found")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "year", "exporter", "importer",
        "exports_usd", "imports_usd", "trade_value_usd", "balance_usd",
        "exporter_gdp_share_pct", "importer_gdp_share_pct", "data_source", "source_credit",
    ])
    for p in pairs:
        e = exp if p.exporter_id == exp.id else imp
        i = imp if p.importer_id == imp.id else exp
        writer.writerow([
            p.year, e.code, i.code,
            p.exports_usd, p.imports_usd, p.trade_value_usd, p.balance_usd,
            p.exporter_gdp_share_pct, p.importer_gdp_share_pct,
            p.data_source or "UN Comtrade", "MetricsHour (metricshour.com)",
        ])

    output.seek(0)
    filename = f"trade-{exporter_code.lower()}-{importer_code.lower()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
