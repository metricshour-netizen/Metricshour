"""add etf, index, bond to assettype enum

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-21
"""
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'etf'")
    op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'index'")
    op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'bond'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op
    pass
