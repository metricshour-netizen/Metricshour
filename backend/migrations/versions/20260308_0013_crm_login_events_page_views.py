"""CRM: add login_events and page_views tables

Revision ID: 20260308_0013
Revises: 20260307_0012
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = '20260308_0013'
down_revision = '20260307_0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'login_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('method', sa.String(20), nullable=False, server_default='password'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_login_events_user_created', 'login_events', ['user_id', 'created_at'])
    op.create_index('ix_login_events_created_at', 'login_events', ['created_at'])

    op.create_table(
        'page_views',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('entity_code', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_page_views_entity', 'page_views', ['entity_type', 'entity_code'])
    op.create_index('ix_page_views_created', 'page_views', ['created_at'])


def downgrade() -> None:
    op.drop_table('page_views')
    op.drop_table('login_events')
