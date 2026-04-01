from sqlalchemy import String, Float, Date, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date

from .base import Base


class EarningsEvent(Base):
    """
    Upcoming/historical earnings reports for tracked stocks.
    Populated by Celery task via yfinance earnings_dates.
    """

    __tablename__ = "earnings_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=True)     # "Q1 2025", "Q4 2024"
    # Estimates (may be null for future events)
    eps_estimate: Mapped[float] = mapped_column(Float, nullable=True)
    eps_actual: Mapped[float] = mapped_column(Float, nullable=True)
    revenue_estimate: Mapped[float] = mapped_column(Float, nullable=True)
    revenue_actual: Mapped[float] = mapped_column(Float, nullable=True)
    surprise_pct: Mapped[float] = mapped_column(Float, nullable=True)  # (actual-estimate)/|estimate|*100

    __table_args__ = (
        UniqueConstraint("symbol", "report_date", name="uq_earnings_symbol_date"),
        Index("ix_earnings_report_date", "report_date"),
        Index("ix_earnings_asset_id", "asset_id"),
    )
