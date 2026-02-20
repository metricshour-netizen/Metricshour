"""widen_currency_symbol

Revision ID: 243eb2a39677
Revises: 0001
Create Date: 2026-02-20 01:33:17.210379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '243eb2a39677'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('countries', 'currency_symbol',
                    type_=sa.String(10),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('countries', 'currency_symbol',
                    type_=sa.String(5),
                    existing_nullable=True)
