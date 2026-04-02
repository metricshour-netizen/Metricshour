"""add fetched_at to prices

Revision ID: 0019_fetched_at
Revises: 0018_earnings_events
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0019_fetched_at'
down_revision = '0018_earnings_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('prices', sa.Column(
        'fetched_at',
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ))


def downgrade() -> None:
    op.drop_column('prices', 'fetched_at')
