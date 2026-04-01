"""
Rates & yield curve API.
Serves FRED macro time-series data from the macro_series table.

GET /api/rates/                      — latest value for each series
GET /api/rates/yield-curve           — current yield curve snapshot
GET /api/rates/{series_id}           — full history for one series
GET /api/rates/{series_id}/latest    — single latest observation
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.macro import MacroSeries

router = APIRouter(tags=["rates"])

# Display order + metadata for the dashboard
SERIES_META: dict[str, dict] = {
    "DFF":          {"label": "Fed Funds Rate",          "unit": "%",    "category": "rates"},
    "DGS3MO":       {"label": "3-Month Treasury",        "unit": "%",    "category": "yield_curve"},
    "DGS2":         {"label": "2-Year Treasury",         "unit": "%",    "category": "yield_curve"},
    "DGS5":         {"label": "5-Year Treasury",         "unit": "%",    "category": "yield_curve"},
    "DGS10":        {"label": "10-Year Treasury",        "unit": "%",    "category": "yield_curve"},
    "DGS30":        {"label": "30-Year Treasury",        "unit": "%",    "category": "yield_curve"},
    "T10Y2Y":       {"label": "10Y–2Y Spread",           "unit": "%",    "category": "yield_curve"},
    "MORTGAGE30US": {"label": "30-Yr Mortgage",          "unit": "%",    "category": "rates"},
    "DFII10":       {"label": "10-Yr Real Rate (TIPS)",  "unit": "%",    "category": "rates"},
    "CPIAUCSL":     {"label": "CPI YoY",                 "unit": "%",    "category": "inflation"},
    "CPILFESL":     {"label": "Core CPI YoY",            "unit": "%",    "category": "inflation"},
    "PCEPI":        {"label": "PCE Price Index",         "unit": "index","category": "inflation"},
    "M2SL":         {"label": "M2 Money Supply",         "unit": "$B",   "category": "money"},
    "ICSA":         {"label": "Initial Jobless Claims",  "unit": "K",    "category": "labor"},
    "UNRATE":       {"label": "Unemployment Rate",       "unit": "%",    "category": "labor"},
}

YIELD_CURVE_SERIES = ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"]
YIELD_CURVE_LABELS = {
    "DGS3MO": "3M",
    "DGS2": "2Y",
    "DGS5": "5Y",
    "DGS10": "10Y",
    "DGS30": "30Y",
}


def _latest_per_series(db: Session, series_ids: list[str]) -> dict[str, MacroSeries]:
    """Return a dict of series_id → latest MacroSeries row for each requested series."""
    subq = (
        select(MacroSeries.series_id, func.max(MacroSeries.period_date).label("max_date"))
        .where(MacroSeries.series_id.in_(series_ids))
        .group_by(MacroSeries.series_id)
        .subquery()
    )
    rows = db.execute(
        select(MacroSeries).join(
            subq,
            (MacroSeries.series_id == subq.c.series_id) &
            (MacroSeries.period_date == subq.c.max_date),
        )
    ).scalars().all()
    return {r.series_id: r for r in rows}


@router.get("/rates/")
def get_rates_dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return latest value for every tracked FRED series, grouped by category."""
    latest = _latest_per_series(db, list(SERIES_META.keys()))

    grouped: dict[str, list] = {}
    for sid, meta in SERIES_META.items():
        cat = meta["category"]
        row = latest.get(sid)
        grouped.setdefault(cat, []).append({
            "series_id": sid,
            "label": meta["label"],
            "unit": meta["unit"],
            "value": row.value if row else None,
            "period_date": row.period_date.isoformat() if row else None,
            "period_type": row.period_type if row else None,
        })

    return {"categories": grouped, "series_count": len(SERIES_META)}


@router.get("/rates/yield-curve")
def get_yield_curve(
    days: int = Query(default=730, ge=30, le=3650),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return yield curve time-series for chart rendering.
    - current: latest snapshot across all maturities
    - history: dict of series_id → [{date, value}] for the last `days` days
    """
    since = date.today() - timedelta(days=days)

    # Current snapshot
    current_latest = _latest_per_series(db, YIELD_CURVE_SERIES)
    current = [
        {
            "maturity": YIELD_CURVE_LABELS[sid],
            "series_id": sid,
            "value": current_latest[sid].value if sid in current_latest else None,
            "period_date": current_latest[sid].period_date.isoformat() if sid in current_latest else None,
        }
        for sid in YIELD_CURVE_SERIES
    ]

    # Historical time-series for sparklines / comparison
    rows = db.execute(
        select(MacroSeries)
        .where(MacroSeries.series_id.in_(YIELD_CURVE_SERIES))
        .where(MacroSeries.period_date >= since)
        .order_by(MacroSeries.series_id, MacroSeries.period_date)
    ).scalars().all()

    history: dict[str, list] = {sid: [] for sid in YIELD_CURVE_SERIES}
    for r in rows:
        history[r.series_id].append({"date": r.period_date.isoformat(), "value": r.value})

    return {
        "current": current,
        "history": history,
        "labels": YIELD_CURVE_LABELS,
        "days": days,
    }


@router.get("/rates/{series_id}")
def get_series_history(
    series_id: str,
    days: int = Query(default=365, ge=7, le=3650),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return time-series history for a single FRED series."""
    sid = series_id.upper()
    if sid not in SERIES_META:
        raise HTTPException(status_code=404, detail=f"Series '{sid}' not found")

    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(MacroSeries)
        .where(MacroSeries.series_id == sid)
        .where(MacroSeries.period_date >= since)
        .order_by(MacroSeries.period_date)
    ).scalars().all()

    data = [{"date": r.period_date.isoformat(), "value": r.value} for r in rows]
    meta = SERIES_META[sid]

    return {
        "series_id": sid,
        "label": meta["label"],
        "unit": meta["unit"],
        "category": meta["category"],
        "days": days,
        "count": len(data),
        "data": data,
        "latest": data[-1] if data else None,
    }


@router.get("/rates/{series_id}/latest")
def get_series_latest(series_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return only the latest observation for a single FRED series."""
    sid = series_id.upper()
    if sid not in SERIES_META:
        raise HTTPException(status_code=404, detail=f"Series '{sid}' not found")

    row = db.execute(
        select(MacroSeries)
        .where(MacroSeries.series_id == sid)
        .order_by(MacroSeries.period_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="No data yet for this series")

    return {
        "series_id": sid,
        "label": SERIES_META[sid]["label"],
        "unit": SERIES_META[sid]["unit"],
        "value": row.value,
        "period_date": row.period_date.isoformat(),
        "period_type": row.period_type,
    }
