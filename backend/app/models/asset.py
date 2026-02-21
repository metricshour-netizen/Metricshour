import enum
from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum, Integer, UniqueConstraint, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class AssetType(str, enum.Enum):
    stock = "stock"
    crypto = "crypto"
    commodity = "commodity"
    fx = "fx"
    etf = "etf"
    index = "index"
    bond = "bond"


class Asset(Base):
    """Unified table for all tradeable instruments."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)             # AAPL, BTC, XAUUSD, EURUSD
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), nullable=True)            # NASDAQ, NYSE, BINANCE
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Stock-specific
    sector: Mapped[str] = mapped_column(String(50), nullable=True)              # Technology, Healthcare
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=True)  # HQ country
    market_cap_usd: Mapped[float] = mapped_column(Float, nullable=True)

    # FX-specific
    base_currency: Mapped[str] = mapped_column(String(3), nullable=True)        # EUR in EURUSD
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=True)       # USD in EURUSD

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    prices: Mapped[list["Price"]] = relationship(back_populates="asset")
    country_revenues: Mapped[list["StockCountryRevenue"]] = relationship(back_populates="asset")
    alerts: Mapped[list["PriceAlert"]] = relationship(back_populates="asset")

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_asset_symbol_exchange"),
        Index("ix_assets_type", "asset_type"),
    )


class Price(Base):
    """OHLCV price history for all asset types."""

    __tablename__ = "prices"
    __table_args__ = (
        # Partitioning by month recommended once volume grows
        Index("ix_prices_asset_timestamp", "asset_id", "timestamp"),
        UniqueConstraint("asset_id", "timestamp", "interval", name="uq_price_asset_time_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval: Mapped[str] = mapped_column(String(5), nullable=False)            # 1m, 15m, 1h, 1d
    open: Mapped[float] = mapped_column(Float, nullable=True)
    high: Mapped[float] = mapped_column(Float, nullable=True)
    low: Mapped[float] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="prices")


class StockCountryRevenue(Base):
    """Geographic revenue breakdown per stock per reporting period (from SEC EDGAR).
    This is MetricsHour's core connector: links stocks to countries."""

    __tablename__ = "stock_country_revenues"
    __table_args__ = (
        UniqueConstraint("asset_id", "country_id", "fiscal_year", "fiscal_quarter",
                         name="uq_stock_country_revenue"),
        Index("ix_stock_country_revenue_asset", "asset_id", "fiscal_year"),
        Index("ix_stock_country_revenue_country", "country_id", "fiscal_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)
    revenue_pct: Mapped[float] = mapped_column(Float, nullable=False)           # 0.0 - 100.0
    revenue_usd: Mapped[float] = mapped_column(Float, nullable=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=True)         # 1-4, null = annual

    asset: Mapped["Asset"] = relationship(back_populates="country_revenues")
    country: Mapped["Country"] = relationship(back_populates="stock_exposures")
