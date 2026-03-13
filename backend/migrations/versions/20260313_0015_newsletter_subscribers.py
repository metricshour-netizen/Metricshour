"""newsletter_subscribers table"""
from alembic import op
import sqlalchemy as sa

revision = '20260313_0015'
down_revision = '20260310_0014'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'newsletter_subscribers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='unknown'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('subscribed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('unsubscribed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_newsletter_email', 'newsletter_subscribers', ['email'], unique=True)
    op.create_index('ix_newsletter_token', 'newsletter_subscribers', ['token'], unique=True)


def downgrade():
    op.drop_table('newsletter_subscribers')
