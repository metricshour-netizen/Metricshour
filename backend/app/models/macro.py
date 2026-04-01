from sqlalchemy import String, Float, Date, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date

from .base import Base


class MacroSeries(Base):
    """
    FRED macro time-series data not tied to a specific country.
    Covers yield curve, Fed funds rate, CPI, M2, unemployment, mortgage rates.
    """

    __tablename__ = "macro_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_id: Mapped[str] = mapped_column(String(30), nullable=False)    # e.g. "DGS10"
    name: Mapped[str] = mapped_column(String(100), nullable=True)         # e.g. "10-Year Treasury"
    category: Mapped[str] = mapped_column(String(30), nullable=True)      # "yield_curve", "rates", "inflation", "money", "labor"
    value: Mapped[float] = mapped_column(Float, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=True)   # "daily", "weekly", "monthly"
    source: Mapped[str] = mapped_column(String(20), nullable=True, default="fred")

    __table_args__ = (
        UniqueConstraint("series_id", "period_date", name="uq_macro_series_date"),
        Index("ix_macro_series_id_date", "series_id", "period_date"),
    )
