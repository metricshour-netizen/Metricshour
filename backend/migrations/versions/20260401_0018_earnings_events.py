"""earnings_events table for stock earnings calendar

Revision ID: 0018_earnings_events
Revises: 0017_macro_series
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_earnings_events"
down_revision = "0017_macro_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("period", sa.String(10), nullable=True),
        sa.Column("eps_estimate", sa.Float(), nullable=True),
        sa.Column("eps_actual", sa.Float(), nullable=True),
        sa.Column("revenue_estimate", sa.Float(), nullable=True),
        sa.Column("revenue_actual", sa.Float(), nullable=True),
        sa.Column("surprise_pct", sa.Float(), nullable=True),
        sa.UniqueConstraint("symbol", "report_date", name="uq_earnings_symbol_date"),
    )
    op.create_index("ix_earnings_report_date", "earnings_events", ["report_date"])
    op.create_index("ix_earnings_asset_id", "earnings_events", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_earnings_asset_id", table_name="earnings_events")
    op.drop_index("ix_earnings_report_date", table_name="earnings_events")
    op.drop_table("earnings_events")
