"""Add UNIQUE constraint to feed_events.source_url

Revision ID: 20260225_0010
Revises: 20260225_0009
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = '20260225_0010'
down_revision = '20260225_0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicates: keep the row with the highest id for each source_url
    op.execute("""
        DELETE FROM feed_events
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM feed_events
            WHERE source_url IS NOT NULL
            GROUP BY source_url
        )
        AND source_url IS NOT NULL
    """)
    op.create_unique_constraint(
        'uq_feed_events_source_url', 'feed_events', ['source_url']
    )


def downgrade() -> None:
    op.drop_constraint('uq_feed_events_source_url', 'feed_events', type_='unique')
