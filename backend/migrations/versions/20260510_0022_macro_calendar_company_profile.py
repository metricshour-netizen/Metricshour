"""macro_calendar_events and company_profiles tables

Revision ID: 0022
Revises: 0021_email_alerts
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021_email_alerts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # macro_calendar_events
    op.create_table(
        'macro_calendar_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('country_code', sa.String(2), nullable=False),
        sa.Column('event_name', sa.String(200), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('impact', sa.String(10), nullable=False, server_default='medium'),
        sa.Column('previous_value', sa.String(50), nullable=True),
        sa.Column('forecast_value', sa.String(50), nullable=True),
        sa.Column('actual_value', sa.String(50), nullable=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('country_code', 'event_name', 'event_date', name='uq_macro_calendar_event'),
    )
    op.create_index('ix_macro_calendar_event_date', 'macro_calendar_events', ['event_date'])
    op.create_index('ix_macro_calendar_country', 'macro_calendar_events', ['country_code'])
    op.create_index('ix_macro_calendar_impact', 'macro_calendar_events', ['impact'])

    # company_profiles
    op.create_table(
        'company_profiles',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('asset_id', sa.Integer, sa.ForeignKey('assets.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, unique=True),
        sa.Column('ceo_name', sa.String(200), nullable=True),
        sa.Column('ceo_since_year', sa.Integer, nullable=True),
        sa.Column('founded_year', sa.Integer, nullable=True),
        sa.Column('hq_city', sa.String(100), nullable=True),
        sa.Column('hq_country_code', sa.String(2), nullable=True),
        sa.Column('employees', sa.BigInteger, nullable=True),
        sa.Column('website', sa.String(300), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_soe', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('chinese_name', sa.String(200), nullable=True),
        sa.Column('pinyin_name', sa.String(200), nullable=True),
        sa.Column('primary_listing', sa.String(10), nullable=True),
        sa.Column('cross_listing', sa.String(200), nullable=True),
        sa.Column('csrc_industry', sa.String(200), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=True),
        sa.Column('last_fetched', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_company_profiles_symbol', 'company_profiles', ['symbol'])


def downgrade() -> None:
    op.drop_table('company_profiles')
    op.drop_table('macro_calendar_events')
