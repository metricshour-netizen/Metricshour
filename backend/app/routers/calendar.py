from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.database import get_db
from app.limiter import limiter
from app.models.macro_calendar import MacroCalendarEvent
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _event_dict(e: MacroCalendarEvent) -> dict:
    return {
        'id': e.id,
        'country_code': e.country_code,
        'event_name': e.event_name,
        'event_type': e.event_type,
        'event_date': e.event_date.isoformat() if e.event_date else None,
        'impact': e.impact,
        'previous_value': e.previous_value,
        'forecast_value': e.forecast_value,
        'actual_value': e.actual_value,
        'source': e.source,
    }


@router.get('')
@limiter.limit('60/minute')
def list_calendar_events(
    request: Request,
    start: str | None = None,
    end: str | None = None,
    country: str | None = None,
    event_type: str | None = None,
    impact: str | None = None,
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """List macro calendar events grouped by day."""
    now = datetime.now(timezone.utc)

    if start:
        try:
            start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        except ValueError:
            start_dt = now
    else:
        start_dt = now

    if end:
        try:
            end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
        except ValueError:
            end_dt = start_dt + timedelta(days=days)
    else:
        end_dt = start_dt + timedelta(days=days)

    cache_key = f'calendar:list:{start_dt.date()}:{end_dt.date()}:{country or "all"}:{event_type or "all"}:{impact or "all"}'
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    filters = [
        MacroCalendarEvent.event_date >= start_dt,
        MacroCalendarEvent.event_date <= end_dt,
    ]
    if country:
        codes = [c.upper().strip() for c in country.split(',') if c.strip()]
        if codes:
            filters.append(MacroCalendarEvent.country_code.in_(codes))
    if event_type:
        filters.append(MacroCalendarEvent.event_type == event_type)
    if impact:
        filters.append(MacroCalendarEvent.impact == impact)

    events = db.execute(
        select(MacroCalendarEvent)
        .where(and_(*filters))
        .order_by(MacroCalendarEvent.event_date)
        .limit(limit)
    ).scalars().all()

    # Group by date
    days_map: dict = {}
    today_str = now.strftime('%Y-%m-%d')
    for e in events:
        day_str = e.event_date.strftime('%Y-%m-%d') if e.event_date else 'unknown'
        if day_str not in days_map:
            days_map[day_str] = {
                'date': day_str,
                'is_today': day_str == today_str,
                'events': [],
            }
        days_map[day_str]['events'].append(_event_dict(e))

    result = {
        'days': list(days_map.values()),
        'total': len(events),
        'start': start_dt.isoformat(),
        'end': end_dt.isoformat(),
    }
    cache_set(cache_key, result, ttl_seconds=3600)
    return result


@router.get('/upcoming')
@limiter.limit('120/minute')
def get_upcoming_events(
    request: Request,
    days: int = Query(default=30, ge=1, le=90),
    country: str | None = None,
    impact: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Get upcoming macro events — used by country pages, stock pages, homepage widget."""
    now = datetime.now(timezone.utc)
    end_dt = now + timedelta(days=days)

    cache_key = f'calendar:upcoming:{days}:{country or "all"}:{impact or "all"}:{limit}'
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    filters = [
        MacroCalendarEvent.event_date >= now,
        MacroCalendarEvent.event_date <= end_dt,
    ]
    if country:
        codes = [c.upper().strip() for c in country.split(',') if c.strip()]
        if codes:
            filters.append(MacroCalendarEvent.country_code.in_(codes))
    if impact:
        filters.append(MacroCalendarEvent.impact == impact)

    events = db.execute(
        select(MacroCalendarEvent)
        .where(and_(*filters))
        .order_by(MacroCalendarEvent.event_date)
        .limit(limit)
    ).scalars().all()

    result = [_event_dict(e) for e in events]
    cache_set(cache_key, result, ttl_seconds=1800)
    return result
