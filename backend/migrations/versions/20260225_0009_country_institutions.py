"""add country_institutions table

Revision ID: 20260225_0009
Revises: 20260225_0008
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = '20260225_0009'
down_revision = '20260225_0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'country_institutions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('country_id', sa.Integer, sa.ForeignKey('countries.id', ondelete='CASCADE'), nullable=False, unique=True),
        # Government
        sa.Column('gov_portal_url', sa.String(500), nullable=True),
        # Central Bank
        sa.Column('central_bank_url', sa.String(500), nullable=True),
        sa.Column('central_bank_name', sa.String(200), nullable=True),
        # Statistics
        sa.Column('stats_office_url', sa.String(500), nullable=True),
        sa.Column('stats_office_name', sa.String(200), nullable=True),
        # Finance
        sa.Column('min_finance_url', sa.String(500), nullable=True),
        # Markets
        sa.Column('stock_exchange_url', sa.String(500), nullable=True),
        sa.Column('stock_exchange_name', sa.String(200), nullable=True),
        # Revenue / Tax
        sa.Column('revenue_authority_url', sa.String(500), nullable=True),
        sa.Column('revenue_authority_name', sa.String(200), nullable=True),
        # Customs
        sa.Column('customs_authority_url', sa.String(500), nullable=True),
        # Trade / Export
        sa.Column('trade_ministry_url', sa.String(500), nullable=True),
        sa.Column('export_promotion_url', sa.String(500), nullable=True),
        # Business
        sa.Column('chamber_of_commerce_url', sa.String(500), nullable=True),
        # Metadata
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_country_institutions_country_id', 'country_institutions', ['country_id'])


def downgrade():
    op.drop_table('country_institutions')
