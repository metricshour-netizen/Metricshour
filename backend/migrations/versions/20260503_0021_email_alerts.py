"""email_alerts table

Revision ID: 0021
Revises: 0020_blog_categories_authors
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa

revision = '0021_email_alerts'
down_revision = '0020_blog_categories_authors'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'email_alerts',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('asset_symbol', sa.String(20), nullable=False),
        sa.Column('asset_name', sa.String(200), nullable=True),
        sa.Column('asset_type', sa.String(20), nullable=False, server_default='stock'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('unsubscribe_token', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_email_alerts_email_asset', 'email_alerts', ['email', 'asset_symbol'])
    op.create_index('ix_email_alerts_token', 'email_alerts', ['unsubscribe_token'])


def downgrade() -> None:
    op.drop_table('email_alerts')
