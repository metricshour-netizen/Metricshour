"""blog_posts table — CRM for editor-authored feed content

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL to avoid SQLAlchemy auto-creating the enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE blogstatus AS ENUM ('draft', 'published');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id              SERIAL PRIMARY KEY,
            title           VARCHAR(300) NOT NULL,
            slug            VARCHAR(300) NOT NULL UNIQUE,
            body            TEXT NOT NULL,
            excerpt         VARCHAR(300),
            cover_image_url VARCHAR(500),
            author_name     VARCHAR(50) NOT NULL DEFAULT 'MetricsHour Team',
            status          blogstatus NOT NULL DEFAULT 'draft',
            related_asset_ids   JSONB,
            related_country_ids JSONB,
            importance_score    FLOAT NOT NULL DEFAULT 5.0,
            published_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL,
            feed_event_id   INTEGER REFERENCES feed_events(id) ON DELETE SET NULL
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_blog_posts_status ON blog_posts (status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_blog_posts_published_at ON blog_posts (published_at);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_blog_posts_published_at")
    op.execute("DROP INDEX IF EXISTS ix_blog_posts_status")
    op.execute("DROP TABLE IF EXISTS blog_posts")
    op.execute("DROP TYPE IF EXISTS blogstatus")
