"""
Feed models — FeedEvent, UserFollow, UserInteraction, BlogPost.

FeedEvent is the content unit in the adaptive feed.
UserFollow captures which assets / countries a user follows.
UserInteraction captures engagement signals (view, click, save, skip, share)
used by the ranking algorithm to personalise the feed.
BlogPost is the internal CRM for editor-authored content.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class FeedEvent(Base):
    """
    A single card in the adaptive feed.

    event_type groups broad categories (price_move, macro_release, article, etc.).
    event_subtype narrows it (e.g. event_type='price_move', event_subtype='crypto').
    importance_score (0–10) is set by the generator based on magnitude / market impact.
    The ranker combines importance_score + recency decay + personalisation signals.
    """

    __tablename__ = "feed_events"
    __table_args__ = (
        Index("ix_feed_events_published_at", "published_at"),
        Index("ix_feed_events_type_subtype", "event_type", "event_subtype"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(String(5000), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    event_subtype: Mapped[str] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # JSONB arrays of integer IDs — [1, 2, 3]
    related_asset_ids: Mapped[list] = mapped_column(JSONB, nullable=True)
    related_country_ids: Mapped[list] = mapped_column(JSONB, nullable=True)

    # Extra structured data (change_pct, indicator_value, etc.) — schema-less on purpose
    # Named event_data not metadata — SQLAlchemy reserves 'metadata' on declarative models
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # 0–10 set by generator: 10 = Fed rate hike, 5 = price moved 3%, 1 = minor update
    importance_score: Mapped[float] = mapped_column(Float, nullable=True, default=0.0)

    # Relationships
    interactions: Mapped[list["UserInteraction"]] = relationship(back_populates="event")


class FollowEntityType(str, enum.Enum):
    asset = "asset"
    country = "country"


class UserFollow(Base):
    """
    A user follows an asset or country.
    Following boosts the score of feed events related to that entity.
    """

    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_user_follow"),
        Index("ix_user_follows_user", "user_id", "entity_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[FollowEntityType] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    followed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="follows")  # type: ignore[name-defined]


class InteractionType(str, enum.Enum):
    view = "view"      # scrolled past (auto-tracked)
    click = "click"    # opened full event
    save = "save"      # bookmarked
    skip = "skip"      # dismissed / swiped away
    share = "share"    # shared externally


class UserInteraction(Base):
    """
    One interaction record per user per feed event (upsert on conflict).
    The most recent / highest-intent interaction wins.

    Interaction weights in ranker:
      save  → +5   (strongest positive signal)
      click → +3
      view  → +1
      skip  → -5   (suppress this event)
      share → +4
    """

    __tablename__ = "user_interactions"
    __table_args__ = (
        UniqueConstraint("user_id", "feed_event_id", name="uq_user_interaction"),
        Index("ix_user_interactions_user", "user_id", "created_at"),
        Index("ix_user_interactions_event", "feed_event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    feed_event_id: Mapped[int] = mapped_column(
        ForeignKey("feed_events.id", ondelete="CASCADE"), nullable=False
    )
    interaction_type: Mapped[InteractionType] = mapped_column(String(10), nullable=False)
    dwell_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="interactions")  # type: ignore[name-defined]
    event: Mapped["FeedEvent"] = relationship(back_populates="interactions")


# Valid blog category slugs — add new ones here + update BLOG_CATEGORIES in admin router
BLOG_CATEGORIES = [
    "macro",        # central banks, rates, inflation, GDP
    "trade",        # trade flows, tariffs, exports/imports
    "markets",      # stocks, indices, equity
    "crypto",       # digital assets
    "commodities",  # oil, gold, metals, agriculture
    "fx",           # currencies, forex
    "geopolitics",  # sanctions, political risk
    "data",         # data deep-dives, statistics
]


class BlogAuthor(Base):
    """Named author profile — referenced by BlogPost.author_slug."""

    __tablename__ = "blog_authors"

    slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    twitter_handle: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    posts: Mapped[list["BlogPost"]] = relationship(back_populates="author")


class BlogStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class BlogPost(Base):
    """
    Internal CRM blog post. When published, a FeedEvent is auto-created
    so the article appears in the adaptive feed.
    """

    __tablename__ = "blog_posts"
    __table_args__ = (
        Index("ix_blog_posts_status", "status"),
        Index("ix_blog_posts_published_at", "published_at"),
        Index("ix_blog_posts_category", "category"),
        Index("ix_blog_posts_author_slug", "author_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(String(300), nullable=True)
    cover_image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    author_name: Mapped[str] = mapped_column(String(50), nullable=False, default="MetricsHour Team")
    author_slug: Mapped[str] = mapped_column(
        String(100), ForeignKey("blog_authors.slug", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[BlogStatus] = mapped_column(
        Enum(BlogStatus, name="blogstatus"), nullable=False, default=BlogStatus.draft
    )
    related_asset_ids: Mapped[list] = mapped_column(JSONB, nullable=True)
    related_country_ids: Mapped[list] = mapped_column(JSONB, nullable=True)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # FK to FeedEvent created on publish (nullable — only set after publish)
    feed_event_id: Mapped[int] = mapped_column(
        ForeignKey("feed_events.id", ondelete="SET NULL"), nullable=True
    )

    author: Mapped["BlogAuthor"] = relationship(back_populates="posts", foreign_keys=[author_slug])
