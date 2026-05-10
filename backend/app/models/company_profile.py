from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from .base import Base


class CompanyProfile(Base):
    __tablename__ = 'company_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey('assets.id', ondelete='CASCADE'), unique=True, nullable=False)
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    ceo_name = Column(String(200), nullable=True)
    ceo_since_year = Column(Integer, nullable=True)
    founded_year = Column(Integer, nullable=True)
    hq_city = Column(String(100), nullable=True)
    hq_country_code = Column(String(2), nullable=True)
    employees = Column(BigInteger, nullable=True)
    website = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    is_soe = Column(Boolean, nullable=False, server_default='false')
    chinese_name = Column(String(200), nullable=True)
    pinyin_name = Column(String(200), nullable=True)
    primary_listing = Column(String(10), nullable=True)       # SSE, SZSE, NYSE, NASDAQ
    cross_listing = Column(String(200), nullable=True)        # e.g. "H-share: 0700.HK"
    csrc_industry = Column(String(200), nullable=True)        # Chinese CSRC classification
    data_source = Column(String(50), nullable=True)           # wikipedia, edgar, manual
    last_fetched = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
