from datetime import datetime

from sqlalchemy import String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PageSummary(Base):
    """50-100 word AI-templated summary for every page. Generated daily by Celery."""

    __tablename__ = "page_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)   # country, stock, commodity, trade, *_insight
    entity_code: Mapped[str] = mapped_column(String(50), nullable=False)   # US, AAPL, US-CN
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_code", name="uq_page_summary"),
        Index("ix_page_summaries_lookup", "entity_type", "entity_code"),
    )


class PageInsight(Base):
    """Daily AI analyst insights — full history kept, one row per day per entity."""

    __tablename__ = "page_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)   # country, stock, commodity
    entity_code: Mapped[str] = mapped_column(String(50), nullable=False)   # US, AAPL
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_page_insights_lookup", "entity_type", "entity_code", "generated_at"),
    )
