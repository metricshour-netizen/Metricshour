"""Smart Money Tracker — institutional investor 13F filing data."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SmartMoneyInvestor(Base):
    """Tracked institutional investors and fund managers."""

    __tablename__ = "smart_money_investors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fund_name: Mapped[str] = mapped_column(String(300), nullable=True)
    cik: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1)   # 1=featured individual, 2=featured fund, 3=all
    description: Mapped[str] = mapped_column(Text, nullable=True)
    aum_usd: Mapped[float] = mapped_column(Float, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    filing_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SmartMoneyFiling(Base):
    """A single 13F-HR filing for one investor/quarter."""

    __tablename__ = "smart_money_filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investor_id: Mapped[int] = mapped_column(ForeignKey("smart_money_investors.id", ondelete="CASCADE"), nullable=False)
    cik: Mapped[str] = mapped_column(String(20), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(30), nullable=True)
    filed_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_of_report: Mapped[date] = mapped_column(Date, nullable=False)    # end of quarter
    quarter_label: Mapped[str] = mapped_column(String(10), nullable=False)  # "Q1 2026"
    total_value_usd: Mapped[float] = mapped_column(Float, nullable=True)
    holding_count: Mapped[int] = mapped_column(Integer, nullable=True)
    parsed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("cik", "period_of_report", name="uq_sm_filing_cik_period"),
        Index("ix_sm_filings_investor", "investor_id"),
        Index("ix_sm_filings_period", "period_of_report"),
    )


class SmartMoneyHolding(Base):
    """Individual stock holding from a 13F filing."""

    __tablename__ = "smart_money_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("smart_money_filings.id", ondelete="CASCADE"), nullable=False)
    investor_id: Mapped[int] = mapped_column(ForeignKey("smart_money_investors.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    company_name: Mapped[str] = mapped_column(String(300), nullable=True)
    cusip: Mapped[str] = mapped_column(String(12), nullable=True)
    shares: Mapped[int] = mapped_column(Integer, nullable=True)
    value_usd: Mapped[float] = mapped_column(Float, nullable=True)
    portfolio_pct: Mapped[float] = mapped_column(Float, nullable=True)     # % of total portfolio
    # Change vs previous quarter
    change_type: Mapped[str] = mapped_column(String(20), nullable=True)    # new/increased/decreased/sold
    shares_change: Mapped[int] = mapped_column(Integer, nullable=True)
    value_change_usd: Mapped[float] = mapped_column(Float, nullable=True)
    quarter_label: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        UniqueConstraint("filing_id", "symbol", name="uq_sm_holding_filing_symbol"),
        Index("ix_sm_holdings_investor", "investor_id"),
        Index("ix_sm_holdings_symbol", "symbol"),
        Index("ix_sm_holdings_quarter", "quarter_label"),
    )
