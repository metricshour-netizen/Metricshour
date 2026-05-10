from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Index
from sqlalchemy.sql import func
from .base import Base


class MacroCalendarEvent(Base):
    __tablename__ = 'macro_calendar_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    country_code = Column(String(2), nullable=False)          # ISO-2 e.g. 'US', 'EU', 'JP'
    event_name = Column(String(200), nullable=False)
    event_type = Column(String(50), nullable=False)           # rate_decision, cpi, gdp, nfp, pmi, trade, retail, housing, g7, opec
    event_date = Column(DateTime(timezone=True), nullable=False)
    impact = Column(String(10), nullable=False, server_default='medium')  # high, medium, low
    previous_value = Column(String(50), nullable=True)
    forecast_value = Column(String(50), nullable=True)
    actual_value = Column(String(50), nullable=True)
    source = Column(String(100), nullable=False)              # 'FRED', 'ECB', 'BOE', 'static'
    source_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('country_code', 'event_name', 'event_date', name='uq_macro_calendar_event'),
        Index('ix_macro_calendar_event_date', 'event_date'),
        Index('ix_macro_calendar_country', 'country_code'),
        Index('ix_macro_calendar_impact', 'impact'),
    )
