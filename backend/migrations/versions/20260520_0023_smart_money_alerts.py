"""add smart_money_alerts table

Revision ID: 0023_smart_money_alerts
Revises: 252d20ca0513
Create Date: 2026-05-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0023_smart_money_alerts'
down_revision: Union[str, None] = '252d20ca0513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'smart_money_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('investor_slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'investor_slug', name='uq_sm_alert_email_slug'),
    )
    op.create_index('ix_sm_alerts_slug', 'smart_money_alerts', ['investor_slug'])
    op.create_index('ix_sm_alerts_active', 'smart_money_alerts', ['active'])


def downgrade() -> None:
    op.drop_index('ix_sm_alerts_active', table_name='smart_money_alerts')
    op.drop_index('ix_sm_alerts_slug', table_name='smart_money_alerts')
    op.drop_table('smart_money_alerts')
