"""feed_engine — user_follows, user_interactions, upgrade feed_events

Revision ID: 0003
Revises: 243eb2a39677
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "243eb2a39677"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # feed_events — upgrade existing table
    # related_asset_ids / related_country_ids: String → JSONB
    # No production data in this table yet (MVP), safe to drop + recreate columns.
    # -------------------------------------------------------------------------
    op.drop_column("feed_events", "related_asset_ids")
    op.drop_column("feed_events", "related_country_ids")

    op.add_column("feed_events", sa.Column("related_asset_ids", JSONB, nullable=True))
    op.add_column("feed_events", sa.Column("related_country_ids", JSONB, nullable=True))
    op.add_column("feed_events", sa.Column("event_subtype", sa.String(50), nullable=True))
    op.add_column("feed_events", sa.Column("importance_score", sa.Float, nullable=True, server_default="0"))
    op.add_column("feed_events", sa.Column("image_url", sa.String(500), nullable=True))
    op.add_column("feed_events", sa.Column("event_data", JSONB, nullable=True))
    # Deduplicate: same event shouldn't be inserted twice
    op.create_index("ix_feed_events_type_subtype", "feed_events", ["event_type", "event_subtype"])

    # -------------------------------------------------------------------------
    # user_follows — track which assets/countries a user follows
    # -------------------------------------------------------------------------
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # entity_type: 'asset' or 'country'
        sa.Column("entity_type", sa.String(20), nullable=False),
        # entity_id: FK to assets.id or countries.id depending on entity_type
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("followed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_user_follow"),
    )
    op.create_index("ix_user_follows_user", "user_follows", ["user_id", "entity_type"])

    # -------------------------------------------------------------------------
    # user_interactions — tracks engagement signals for the feed algorithm
    # -------------------------------------------------------------------------
    op.create_table(
        "user_interactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feed_event_id", sa.Integer, sa.ForeignKey("feed_events.id", ondelete="CASCADE"), nullable=False),
        # interaction_type: view, click, save, skip, share
        sa.Column("interaction_type", sa.String(10), nullable=False),
        sa.Column("dwell_seconds", sa.Integer, nullable=True),  # how long they read it
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # One interaction record per user per event — upsert on conflict
        sa.UniqueConstraint("user_id", "feed_event_id", name="uq_user_interaction"),
    )
    op.create_index("ix_user_interactions_user", "user_interactions", ["user_id", "created_at"])
    op.create_index("ix_user_interactions_event", "user_interactions", ["feed_event_id"])


def downgrade() -> None:
    op.drop_table("user_interactions")
    op.drop_table("user_follows")

    op.drop_column("feed_events", "event_data")
    op.drop_column("feed_events", "image_url")
    op.drop_column("feed_events", "importance_score")
    op.drop_column("feed_events", "event_subtype")
    op.drop_column("feed_events", "related_country_ids")
    op.drop_column("feed_events", "related_asset_ids")
    op.add_column("feed_events", sa.Column("related_asset_ids", sa.String(200), nullable=True))
    op.add_column("feed_events", sa.Column("related_country_ids", sa.String(200), nullable=True))
