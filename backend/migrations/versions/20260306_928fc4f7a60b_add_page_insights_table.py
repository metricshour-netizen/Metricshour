"""add page_insights table

Revision ID: 928fc4f7a60b
Revises: 9fd62528d83d
Create Date: 2026-03-06 21:50:34.530008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '928fc4f7a60b'
down_revision: Union[str, None] = '9fd62528d83d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('page_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=False),
        sa.Column('entity_code', sa.String(length=50), nullable=False),
        sa.Column('summary', sa.String(length=2000), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_page_insights_lookup', 'page_insights', ['entity_type', 'entity_code', 'generated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_page_insights_lookup', table_name='page_insights')
    op.drop_table('page_insights')
