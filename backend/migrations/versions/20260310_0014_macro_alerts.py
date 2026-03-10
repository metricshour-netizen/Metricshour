"""macro_alerts table"""
from alembic import op
import sqlalchemy as sa

revision = '20260310_0014'
down_revision = '20260308_0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'macro_alerts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('country_code', sa.String(3), nullable=False),
        sa.Column('indicator_name', sa.String(100), nullable=False),
        sa.Column('condition', sa.String(5), nullable=False),  # 'above' | 'below'
        sa.Column('threshold', sa.Numeric(15, 4), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('cooldown_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_macro_alerts_user', 'macro_alerts', ['user_id'])
    op.create_index('ix_macro_alerts_active', 'macro_alerts',
                    ['is_active', 'country_code', 'indicator_name'])


def downgrade():
    op.drop_index('ix_macro_alerts_active', table_name='macro_alerts')
    op.drop_index('ix_macro_alerts_user', table_name='macro_alerts')
    op.drop_table('macro_alerts')
