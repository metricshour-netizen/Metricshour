"""add feedback table

Revision ID: 20260225_0008
Revises: 20260224_aa855a24463e
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = '20260225_0008'
down_revision = 'aa855a24463e'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('page_url', sa.String(500), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_feedback_created_at', 'feedback', ['created_at'])

def downgrade():
    op.drop_table('feedback')
