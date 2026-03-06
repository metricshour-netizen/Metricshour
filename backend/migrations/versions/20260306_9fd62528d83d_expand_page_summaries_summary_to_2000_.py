"""expand page_summaries summary to 2000 chars and entity_type to 30

Revision ID: 9fd62528d83d
Revises: 20260306_0011
Create Date: 2026-03-06 20:54:16.101380

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '9fd62528d83d'
down_revision: Union[str, None] = '20260306_0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('page_summaries', 'entity_type',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=30),
               existing_nullable=False)
    op.alter_column('page_summaries', 'summary',
               existing_type=sa.VARCHAR(length=800),
               type_=sa.String(length=2000),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('page_summaries', 'summary',
               existing_type=sa.String(length=2000),
               type_=sa.VARCHAR(length=800),
               existing_nullable=False)
    op.alter_column('page_summaries', 'entity_type',
               existing_type=sa.String(length=30),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False)
