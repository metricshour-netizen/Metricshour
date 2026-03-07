"""add data_source column to trade_pairs

Revision ID: 20260307_0012
Revises: 928fc4f7a60b
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = '20260307_0012'
down_revision = '928fc4f7a60b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('trade_pairs', sa.Column('data_source', sa.String(30), nullable=True))
    # Back-fill existing rows — all seeded data is 2022 WTO/IMF
    op.execute("UPDATE trade_pairs SET data_source = 'UN Comtrade 2022' WHERE year = 2022")


def downgrade() -> None:
    op.drop_column('trade_pairs', 'data_source')
