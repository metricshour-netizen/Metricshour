"""macro_series table for FRED rates/yield curve data

Revision ID: 0017_macro_series
Revises: 20260331_0016
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0017_macro_series"
down_revision = "20260331_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_series",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("series_id", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("category", sa.String(30), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=True),
        sa.Column("source", sa.String(20), nullable=True, server_default="fred"),
        sa.UniqueConstraint("series_id", "period_date", name="uq_macro_series_date"),
    )
    op.create_index("ix_macro_series_id_date", "macro_series", ["series_id", "period_date"])


def downgrade() -> None:
    op.drop_index("ix_macro_series_id_date", table_name="macro_series")
    op.drop_table("macro_series")
