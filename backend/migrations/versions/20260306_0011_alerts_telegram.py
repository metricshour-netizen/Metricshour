"""add telegram fields to users and alert_deliveries table

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = '20260306_0011'
down_revision = '20260225_0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Telegram + notification preference columns to users
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('notify_telegram', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('notify_email', sa.Boolean(), nullable=False, server_default='true'))

    # alert_deliveries — tracks every notification sent, prevents duplicates
    op.create_table(
        'alert_deliveries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('alert_id', sa.Integer(), sa.ForeignKey('price_alerts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),          # 'telegram' | 'email'
        sa.Column('price_at_trigger', sa.Float(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
    )
    op.create_index('idx_alert_deliveries_alert_id', 'alert_deliveries', ['alert_id'])
    op.create_index('idx_alert_deliveries_user_id', 'alert_deliveries', ['user_id'])
    op.create_index('idx_alert_deliveries_triggered_at', 'alert_deliveries', ['triggered_at'])


def downgrade() -> None:
    op.drop_table('alert_deliveries')
    op.drop_column('users', 'notify_email')
    op.drop_column('users', 'notify_telegram')
    op.drop_column('users', 'telegram_chat_id')
