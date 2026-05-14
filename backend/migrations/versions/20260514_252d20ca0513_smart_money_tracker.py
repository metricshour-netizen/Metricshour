"""smart_money_tracker

Revision ID: 252d20ca0513
Revises: 0022
Create Date: 2026-05-14 05:30:50.170330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '252d20ca0513'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('smart_money_investors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('fund_name', sa.String(300), nullable=True),
        sa.Column('cik', sa.String(20), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('aum_usd', sa.Float(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('last_filing_date', sa.Date(), nullable=True),
        sa.Column('filing_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.UniqueConstraint('cik'),
    )

    op.create_table('smart_money_filings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('investor_id', sa.Integer(), nullable=False),
        sa.Column('cik', sa.String(20), nullable=False),
        sa.Column('accession_number', sa.String(30), nullable=True),
        sa.Column('filed_date', sa.Date(), nullable=False),
        sa.Column('period_of_report', sa.Date(), nullable=False),
        sa.Column('quarter_label', sa.String(10), nullable=False),
        sa.Column('total_value_usd', sa.Float(), nullable=True),
        sa.Column('holding_count', sa.Integer(), nullable=True),
        sa.Column('parsed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['investor_id'], ['smart_money_investors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cik', 'period_of_report', name='uq_sm_filing_cik_period'),
    )
    op.create_index('ix_sm_filings_investor', 'smart_money_filings', ['investor_id'])
    op.create_index('ix_sm_filings_period', 'smart_money_filings', ['period_of_report'])

    op.create_table('smart_money_holdings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filing_id', sa.Integer(), nullable=False),
        sa.Column('investor_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('company_name', sa.String(300), nullable=True),
        sa.Column('cusip', sa.String(12), nullable=True),
        sa.Column('shares', sa.Integer(), nullable=True),
        sa.Column('value_usd', sa.Float(), nullable=True),
        sa.Column('portfolio_pct', sa.Float(), nullable=True),
        sa.Column('change_type', sa.String(20), nullable=True),
        sa.Column('shares_change', sa.Integer(), nullable=True),
        sa.Column('value_change_usd', sa.Float(), nullable=True),
        sa.Column('quarter_label', sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(['filing_id'], ['smart_money_filings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investor_id'], ['smart_money_investors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filing_id', 'symbol', name='uq_sm_holding_filing_symbol'),
    )
    op.create_index('ix_sm_holdings_investor', 'smart_money_holdings', ['investor_id'])
    op.create_index('ix_sm_holdings_symbol', 'smart_money_holdings', ['symbol'])
    op.create_index('ix_sm_holdings_quarter', 'smart_money_holdings', ['quarter_label'])


def downgrade() -> None:
    op.drop_table('smart_money_holdings')
    op.drop_table('smart_money_filings')
    op.drop_table('smart_money_investors')
