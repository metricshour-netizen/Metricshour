"""sticky price alerts (cooldown + repeat) + discord_webhook_url on users"""
from alembic import op
import sqlalchemy as sa

revision = '20260331_0016'
down_revision = '20260313_0015'
branch_labels = None
depends_on = None


def upgrade():
    # Make price alerts repeatable: cooldown_hours + trigger_count
    op.add_column('price_alerts',
        sa.Column('cooldown_hours', sa.Integer(), nullable=False, server_default='24'))
    op.add_column('price_alerts',
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'))

    # Discord webhook on users
    op.add_column('users',
        sa.Column('discord_webhook_url', sa.String(500), nullable=True))
    op.add_column('users',
        sa.Column('notify_discord', sa.Boolean(), nullable=False, server_default='false'))

    # alert_deliveries: widen channel column to accept 'discord'
    op.alter_column('alert_deliveries', 'channel',
        existing_type=sa.String(20), type_=sa.String(30), nullable=False)


def downgrade():
    op.drop_column('price_alerts', 'cooldown_hours')
    op.drop_column('price_alerts', 'trigger_count')
    op.drop_column('users', 'discord_webhook_url')
    op.drop_column('users', 'notify_discord')
    op.alter_column('alert_deliveries', 'channel',
        existing_type=sa.String(30), type_=sa.String(20), nullable=False)
