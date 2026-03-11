"""
Market hours helpers — used to skip API calls when no fresh data is available.
All time logic is in UTC. No holiday calendar (minor savings not worth complexity).
"""
from datetime import datetime, timezone


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_trading_day(dt: datetime | None = None) -> bool:
    """True Mon–Fri UTC. Excludes weekends; does not check public holidays."""
    if dt is None:
        dt = _now_utc()
    return dt.weekday() < 5  # 0=Mon … 4=Fri


def is_us_market_open(dt: datetime | None = None) -> bool:
    """
    True during approximate NYSE core hours in UTC.
    Standard time:  14:30–21:00 UTC
    Daylight saving: 13:30–20:00 UTC
    We use the wider 13:30–21:00 UTC window so we never miss an open tick.
    """
    if dt is None:
        dt = _now_utc()
    if dt.weekday() >= 5:
        return False
    h, m = dt.hour, dt.minute
    minutes = h * 60 + m
    return 13 * 60 + 30 <= minutes < 21 * 60


def should_call_marketstack_eod(dt: datetime | None = None) -> bool:
    """
    Marketstack /eod/latest returns today's authoritative close only AFTER the
    US market has closed and data has settled (~21:00 UTC).
    During market hours it just returns yesterday's close — a wasted API call.
    Only returns True Mon–Fri between 21:00–23:59 UTC.
    """
    if dt is None:
        dt = _now_utc()
    if dt.weekday() >= 5:
        return False
    return dt.hour >= 21


def is_commodity_market_open(dt: datetime | None = None) -> bool:
    """
    CME/NYMEX futures trade nearly 24 h on weekdays + Sunday evening.
    Closed: Sat 00:00 UTC through Sun 22:00 UTC (≈ Fri 5pm ET → Sun 6pm ET).
    """
    if dt is None:
        dt = _now_utc()
    wd = dt.weekday()
    if wd == 5:            # Saturday — always closed
        return False
    if wd == 6 and dt.hour < 22:   # Sunday before 22:00 UTC — still closed
        return False
    return True
