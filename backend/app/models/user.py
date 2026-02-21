import enum
from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class UserTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    analyst = "analyst"
    enterprise = "enterprise"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)     # Argon2
    tier: Mapped[UserTier] = mapped_column(Enum(UserTier), default=UserTier.free)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    alerts: Mapped[list["PriceAlert"]] = relationship(back_populates="user")
    follows: Mapped[list["UserFollow"]] = relationship(back_populates="user")  # type: ignore[name-defined]
    interactions: Mapped[list["UserInteraction"]] = relationship(back_populates="user")  # type: ignore[name-defined]


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    condition: Mapped[str] = mapped_column(String(5), nullable=False)           # above, below
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="alerts")
    asset: Mapped["Asset"] = relationship(back_populates="alerts")


# FeedEvent moved to models/feed.py
