"""Smart Money Tracker API.

GET /api/smartmoney/investors            — list all tracked investors
GET /api/smartmoney/investors/{slug}     — portfolio for one investor
GET /api/smartmoney/investors/{slug}/holdings?quarter=Q1+2026
GET /api/smartmoney/investors/{slug}/changes?quarter=Q1+2026
GET /api/smartmoney/holders/{symbol}     — who holds a given stock
GET /api/smartmoney/top-buys            — top new/increased positions this quarter
GET /api/smartmoney/top-sells           — top decreased/sold positions this quarter
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func as sqlfunc, and_, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.smart_money import SmartMoneyInvestor, SmartMoneyFiling, SmartMoneyHolding
from app.models.asset import Asset, AssetType, StockCountryRevenue
from app.models.country import Country
from app.storage import cache_get, cache_set

log = logging.getLogger(__name__)
router = APIRouter(prefix="/smartmoney", tags=["smart_money"])

RISK_LABELS = {
    "CN": "145% US tariffs — direct earnings risk",
    "RU": "Sanctions — restricted market",
    "IR": "Sanctions — restricted market",
    "TW": "Geopolitical risk with China elevated",
    "MX": "USMCA tariff uncertainty",
    "TR": "Currency stress, inflation >50%",
    "KR": "US-China trade friction exposure",
    "IN": "Import tariff risks, elevated inflation",
    "AR": "Currency crisis, capital controls",
    "DE": "Industrial slowdown, energy costs",
    "JP": "BOJ rate normalisation underway",
}


def _investor_summary(inv: SmartMoneyInvestor, latest_filing: Optional[SmartMoneyFiling] = None) -> dict:
    return {
        "id": inv.id,
        "slug": inv.slug,
        "name": inv.name,
        "fund_name": inv.fund_name,
        "cik": inv.cik,
        "tier": inv.tier,
        "description": inv.description,
        "aum_usd": inv.aum_usd,
        "avatar_url": inv.avatar_url,
        "last_filing_date": inv.last_filing_date.isoformat() if inv.last_filing_date else None,
        "filing_count": inv.filing_count or 0,
        "latest_quarter": latest_filing.quarter_label if latest_filing else None,
        "total_value_usd": latest_filing.total_value_usd if latest_filing else None,
        "holding_count": latest_filing.holding_count if latest_filing else None,
    }


def _holding_dict(h: SmartMoneyHolding) -> dict:
    return {
        "symbol": h.symbol,
        "company_name": h.company_name,
        "shares": h.shares,
        "value_usd": h.value_usd,
        "portfolio_pct": round(h.portfolio_pct, 2) if h.portfolio_pct else None,
        "change_type": h.change_type,
        "shares_change": h.shares_change,
        "value_change_usd": h.value_change_usd,
        "quarter_label": h.quarter_label,
    }


@router.get("/investors")
@limiter.limit("60/minute")
def list_investors(
    request: Request,
    tier: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List all tracked investors with latest filing summary."""
    cache_key = f"smartmoney:investors:{tier or 'all'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = select(SmartMoneyInvestor).where(SmartMoneyInvestor.active == True)
    if tier:
        query = query.where(SmartMoneyInvestor.tier == tier)
    query = query.order_by(SmartMoneyInvestor.tier, SmartMoneyInvestor.name)
    investors = db.execute(query).scalars().all()

    result = []
    for inv in investors:
        latest_filing = db.execute(
            select(SmartMoneyFiling)
            .where(SmartMoneyFiling.investor_id == inv.id)
            .order_by(SmartMoneyFiling.period_of_report.desc())
            .limit(1)
        ).scalar_one_or_none()
        summary = _investor_summary(inv, latest_filing)

        # Top 3 holdings for the card
        top_holdings: list[str] = []
        if latest_filing:
            top = db.execute(
                select(SmartMoneyHolding.symbol)
                .where(SmartMoneyHolding.filing_id == latest_filing.id)
                .where(SmartMoneyHolding.symbol != "")
                .order_by(SmartMoneyHolding.value_usd.desc().nullslast())
                .limit(3)
            ).scalars().all()
            top_holdings = list(top)
        summary["top_holdings"] = top_holdings
        result.append(summary)

    cache_set(cache_key, result, ttl_seconds=7776000)   # 90 days
    return result


@router.get("/investors/{slug}")
@limiter.limit("60/minute")
def get_investor(
    request: Request,
    slug: str,
    quarter: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Full portfolio for one investor."""
    cache_key = f"smartmoney:investor:{slug}:{quarter or 'latest'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    inv = db.execute(
        select(SmartMoneyInvestor)
        .where(SmartMoneyInvestor.slug == slug)
        .where(SmartMoneyInvestor.active == True)
    ).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investor not found")

    # Find the target filing
    filing_query = select(SmartMoneyFiling).where(SmartMoneyFiling.investor_id == inv.id)
    if quarter:
        filing_query = filing_query.where(SmartMoneyFiling.quarter_label == quarter)
    else:
        filing_query = filing_query.order_by(SmartMoneyFiling.period_of_report.desc())
    filing = db.execute(filing_query.limit(1)).scalar_one_or_none()

    if not filing:
        result = {**_investor_summary(inv), "holdings": [], "changes": {}, "quarters": []}
        return result

    # All available quarters for this investor
    quarters = db.execute(
        select(SmartMoneyFiling.quarter_label)
        .where(SmartMoneyFiling.investor_id == inv.id)
        .order_by(SmartMoneyFiling.period_of_report.desc())
        .limit(8)
    ).scalars().all()

    # Holdings for this filing, sorted by value
    holdings_rows = db.execute(
        select(SmartMoneyHolding)
        .where(SmartMoneyHolding.filing_id == filing.id)
        .order_by(SmartMoneyHolding.value_usd.desc().nullslast())
    ).scalars().all()

    holdings = [_holding_dict(h) for h in holdings_rows]

    # Changes grouped by type
    changes: dict[str, list[dict]] = {"new": [], "increased": [], "decreased": [], "sold": []}
    for h in holdings_rows:
        if h.change_type in changes:
            changes[h.change_type].append(_holding_dict(h))

    summary = _investor_summary(inv, filing)
    result = {
        **summary,
        "holdings": holdings,
        "changes": changes,
        "quarters": list(quarters),
    }
    cache_set(cache_key, result, ttl_seconds=7776000)   # 90 days
    return result


@router.get("/holders/{symbol}")
@limiter.limit("120/minute")
def get_holders(
    request: Request,
    symbol: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Who holds a given stock (top institutional holders)."""
    sym = symbol.upper()
    cache_key = f"smartmoney:holders:{sym}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Get most recent holding per investor for this symbol
    subq = (
        select(
            SmartMoneyHolding.investor_id,
            sqlfunc.max(SmartMoneyFiling.period_of_report).label("latest_period"),
        )
        .join(SmartMoneyFiling, SmartMoneyHolding.filing_id == SmartMoneyFiling.id)
        .where(SmartMoneyHolding.symbol == sym)
        .group_by(SmartMoneyHolding.investor_id)
        .subquery()
    )

    rows = db.execute(
        select(SmartMoneyHolding, SmartMoneyInvestor, SmartMoneyFiling)
        .join(SmartMoneyInvestor, SmartMoneyHolding.investor_id == SmartMoneyInvestor.id)
        .join(SmartMoneyFiling, SmartMoneyHolding.filing_id == SmartMoneyFiling.id)
        .join(
            subq,
            and_(
                SmartMoneyHolding.investor_id == subq.c.investor_id,
                SmartMoneyFiling.period_of_report == subq.c.latest_period,
            ),
        )
        .where(SmartMoneyHolding.symbol == sym)
        .order_by(SmartMoneyHolding.value_usd.desc().nullslast())
        .limit(limit)
    ).all()

    result = []
    for holding, inv, filing in rows:
        result.append({
            "investor_slug": inv.slug,
            "investor_name": inv.name,
            "fund_name": inv.fund_name,
            "shares": holding.shares,
            "value_usd": holding.value_usd,
            "portfolio_pct": round(holding.portfolio_pct, 2) if holding.portfolio_pct else None,
            "change_type": holding.change_type,
            "quarter_label": holding.quarter_label,
        })

    cache_set(cache_key, result, ttl_seconds=7776000)
    return result


@router.get("/top-buys")
@limiter.limit("60/minute")
def top_buys(
    request: Request,
    quarter: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Top new and increased positions across all tracked investors."""
    cache_key = f"smartmoney:top-buys:{quarter or 'latest'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # If no quarter specified, use the most recent quarter that has data
    if not quarter:
        latest_q = db.execute(
            select(SmartMoneyFiling.quarter_label)
            .order_by(SmartMoneyFiling.period_of_report.desc())
            .limit(1)
        ).scalar_one_or_none()
        quarter = latest_q

    rows = db.execute(
        select(SmartMoneyHolding, SmartMoneyInvestor)
        .join(SmartMoneyInvestor, SmartMoneyHolding.investor_id == SmartMoneyInvestor.id)
        .where(SmartMoneyHolding.quarter_label == quarter)
        .where(SmartMoneyHolding.change_type.in_(["new", "increased"]))
        .where(SmartMoneyHolding.value_usd.isnot(None))
        .order_by(SmartMoneyHolding.value_usd.desc())
        .limit(limit)
    ).all()

    result = [{
        **_holding_dict(h),
        "investor_name": inv.name,
        "investor_slug": inv.slug,
    } for h, inv in rows]

    cache_set(cache_key, result, ttl_seconds=7776000)
    return result


@router.get("/top-sells")
@limiter.limit("60/minute")
def top_sells(
    request: Request,
    quarter: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Top decreased and sold-out positions."""
    cache_key = f"smartmoney:top-sells:{quarter or 'latest'}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    if not quarter:
        latest_q = db.execute(
            select(SmartMoneyFiling.quarter_label)
            .order_by(SmartMoneyFiling.period_of_report.desc())
            .limit(1)
        ).scalar_one_or_none()
        quarter = latest_q

    rows = db.execute(
        select(SmartMoneyHolding, SmartMoneyInvestor)
        .join(SmartMoneyInvestor, SmartMoneyHolding.investor_id == SmartMoneyInvestor.id)
        .where(SmartMoneyHolding.quarter_label == quarter)
        .where(SmartMoneyHolding.change_type.in_(["decreased", "sold"]))
        .where(SmartMoneyHolding.value_usd.isnot(None))
        .order_by(SmartMoneyHolding.value_change_usd.asc().nullslast())
        .limit(limit)
    ).all()

    result = [{
        **_holding_dict(h),
        "investor_name": inv.name,
        "investor_slug": inv.slug,
    } for h, inv in rows]

    cache_set(cache_key, result, ttl_seconds=7776000)
    return result
