"""
Earnings calendar API.

GET /api/earnings/upcoming          — next 30 days, grouped by week
GET /api/earnings/recent            — last 14 days (actuals available)
GET /api/earnings/stocks/{symbol}   — history for one stock
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.earnings import EarningsEvent
from app.models.asset import Asset

router = APIRouter(tags=["earnings"])


def _event_dict(ev: EarningsEvent, asset: Asset | None = None) -> dict:
    return {
        "symbol": ev.symbol,
        "name": asset.name if asset else ev.symbol,
        "sector": asset.sector if asset else None,
        "market_cap_usd": asset.market_cap_usd if asset else None,
        "report_date": ev.report_date.isoformat(),
        "period": ev.period,
        "eps_estimate": ev.eps_estimate,
        "eps_actual": ev.eps_actual,
        "revenue_estimate": ev.revenue_estimate,
        "revenue_actual": ev.revenue_actual,
        "surprise_pct": ev.surprise_pct,
    }


def _week_label(d: date) -> str:
    """Return ISO week label like 'Week of Apr 7'."""
    # Find Monday of the week
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("Week of %b %-d")


@router.get("/earnings/upcoming")
def get_upcoming_earnings(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return upcoming earnings events grouped by calendar week."""
    today = date.today()
    until = today + timedelta(days=days)

    rows = db.execute(
        select(EarningsEvent, Asset)
        .join(Asset, EarningsEvent.asset_id == Asset.id, isouter=True)
        .where(EarningsEvent.report_date >= today)
        .where(EarningsEvent.report_date <= until)
        .order_by(EarningsEvent.report_date, Asset.market_cap_usd.desc())
    ).all()

    weeks: dict[str, list] = {}
    for ev, asset in rows:
        label = _week_label(ev.report_date)
        weeks.setdefault(label, []).append(_event_dict(ev, asset))

    return {
        "days": days,
        "total": sum(len(v) for v in weeks.values()),
        "weeks": [{"label": k, "events": v} for k, v in weeks.items()],
    }


@router.get("/earnings/recent")
def get_recent_earnings(
    days: int = Query(default=14, ge=1, le=60),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent earnings with actuals — sorted by surprise % descending."""
    today = date.today()
    since = today - timedelta(days=days)

    rows = db.execute(
        select(EarningsEvent, Asset)
        .join(Asset, EarningsEvent.asset_id == Asset.id, isouter=True)
        .where(EarningsEvent.report_date >= since)
        .where(EarningsEvent.report_date < today)
        .where(EarningsEvent.eps_actual.isnot(None))
        .order_by(EarningsEvent.surprise_pct.desc().nullslast())
    ).all()

    return {
        "days": days,
        "total": len(rows),
        "events": [_event_dict(ev, asset) for ev, asset in rows],
    }


@router.get("/earnings/stocks/{symbol}")
def get_stock_earnings(symbol: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return earnings history for a single stock."""
    sym = symbol.upper()
    asset = db.execute(select(Asset).where(Asset.symbol == sym)).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found")

    rows = db.execute(
        select(EarningsEvent)
        .where(EarningsEvent.symbol == sym)
        .order_by(EarningsEvent.report_date.desc())
        .limit(20)
    ).scalars().all()

    return {
        "symbol": sym,
        "name": asset.name,
        "events": [_event_dict(ev) for ev in rows],
    }
