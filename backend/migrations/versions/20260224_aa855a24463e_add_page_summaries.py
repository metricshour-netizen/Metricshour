"""add_page_summaries

Revision ID: aa855a24463e
Revises: 0006
Create Date: 2026-02-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'aa855a24463e'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'page_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_code', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.String(length=800), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_code', name='uq_page_summary'),
    )
    op.create_index('ix_page_summaries_lookup', 'page_summaries', ['entity_type', 'entity_code'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_page_summaries_lookup', table_name='page_summaries')
    op.drop_table('page_summaries')
