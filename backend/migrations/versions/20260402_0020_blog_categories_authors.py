"""blog_categories_authors

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0020_blog_categories_authors'
down_revision = '0019_fetched_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── blog_authors ──────────────────────────────────────────────────────────
    op.create_table(
        'blog_authors',
        sa.Column('slug', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(150), nullable=True),
        sa.Column('bio', sa.Text, nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('twitter_handle', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Seed the two standard authors
    op.execute("""
        INSERT INTO blog_authors (slug, name, title, bio, created_at)
        VALUES
          ('metricshour-team',     'MetricsHour Team',     'Editorial Team',
           'Market intelligence and data analysis from the MetricsHour editorial team.',
           NOW()),
          ('metricshour-research', 'MetricsHour Research', 'Research Desk',
           'In-depth quantitative analysis and data-driven financial research from our quant team.',
           NOW())
        ON CONFLICT DO NOTHING
    """)

    # ── blog_posts: add category + author_slug ────────────────────────────────
    op.add_column('blog_posts', sa.Column('category', sa.String(50), nullable=True))
    op.add_column(
        'blog_posts',
        sa.Column(
            'author_slug',
            sa.String(100),
            sa.ForeignKey('blog_authors.slug', ondelete='SET NULL'),
            nullable=True,
        ),
    )

    # Backfill author_slug for all existing posts
    op.execute("""
        UPDATE blog_posts
        SET author_slug = 'metricshour-team'
        WHERE author_name = 'MetricsHour Team' AND author_slug IS NULL
    """)
    op.execute("""
        UPDATE blog_posts
        SET author_slug = 'metricshour-research'
        WHERE author_name = 'MetricsHour Research' AND author_slug IS NULL
    """)

    op.create_index('ix_blog_posts_category', 'blog_posts', ['category'])
    op.create_index('ix_blog_posts_author_slug', 'blog_posts', ['author_slug'])


def downgrade() -> None:
    op.drop_index('ix_blog_posts_author_slug', table_name='blog_posts')
    op.drop_index('ix_blog_posts_category', table_name='blog_posts')
    op.drop_column('blog_posts', 'author_slug')
    op.drop_column('blog_posts', 'category')
    op.drop_table('blog_authors')
