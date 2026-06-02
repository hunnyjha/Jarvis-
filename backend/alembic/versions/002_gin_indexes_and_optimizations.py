"""Add GIN indexes for full-text search and performance optimizations.

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # GIN indexes on text fields for fast full-text search
    op.execute("""
        CREATE INDEX ix_memories_content_gin
        ON memories USING gin(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,'')))
    """)
    op.execute("""
        CREATE INDEX ix_research_sessions_query_gin
        ON research_sessions USING gin(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(query,'')))
    """)
    op.execute("""
        CREATE INDEX ix_reddit_posts_title_gin
        ON reddit_posts USING gin(to_tsvector('english', coalesce(title,'')))
    """)
    op.execute("""
        CREATE INDEX ix_security_investigations_target_trgm
        ON security_investigations USING gin(target gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX ix_memories_title_trgm
        ON memories USING gin(title gin_trgm_ops)
    """)

    # Partial indexes for performance on common filtered queries
    op.execute("""
        CREATE INDEX ix_memories_active
        ON memories (user_id, created_at DESC)
        WHERE is_archived = false
    """)
    op.execute("""
        CREATE INDEX ix_memories_pinned
        ON memories (user_id, importance_score DESC)
        WHERE is_pinned = true AND is_archived = false
    """)
    op.execute("""
        CREATE INDEX ix_research_completed
        ON research_sessions (user_id, created_at DESC)
        WHERE status = 'completed'
    """)
    op.execute("""
        CREATE INDEX ix_subreddit_analyses_completed
        ON subreddit_analyses (user_id, created_at DESC)
        WHERE status = 'completed'
    """)
    op.execute("""
        CREATE INDEX ix_reports_completed
        ON reports (user_id, created_at DESC)
        WHERE status = 'completed'
    """)

    # Composite indexes for pagination queries
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index("ix_reddit_posts_score", "reddit_posts", ["analysis_id", "score"])
    op.create_index("ix_topic_discoveries_relevance", "topic_discoveries", ["analysis_id", "relevance_score"])
    op.create_index("ix_security_findings_inv_severity", "security_findings", ["investigation_id", "severity"])

    # Updated_at trigger function for auto-updating timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    for table in [
        "users", "research_sessions", "research_results",
        "subreddit_analyses", "topic_discoveries", "reddit_posts",
        "security_investigations", "security_findings",
        "memory_collections", "memories", "reports", "audit_logs",
    ]:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """)


def downgrade() -> None:
    for table in [
        "users", "research_sessions", "research_results",
        "subreddit_analyses", "topic_discoveries", "reddit_posts",
        "security_investigations", "security_findings",
        "memory_collections", "memories", "reports", "audit_logs",
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}")

    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_index("ix_security_findings_inv_severity", "security_findings")
    op.drop_index("ix_topic_discoveries_relevance", "topic_discoveries")
    op.drop_index("ix_reddit_posts_score", "reddit_posts")
    op.drop_index("ix_audit_logs_user_created", "audit_logs")
    op.execute("DROP INDEX IF EXISTS ix_reports_completed")
    op.execute("DROP INDEX IF EXISTS ix_subreddit_analyses_completed")
    op.execute("DROP INDEX IF EXISTS ix_research_completed")
    op.execute("DROP INDEX IF EXISTS ix_memories_pinned")
    op.execute("DROP INDEX IF EXISTS ix_memories_active")
    op.execute("DROP INDEX IF EXISTS ix_memories_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_security_investigations_target_trgm")
    op.execute("DROP INDEX IF EXISTS ix_reddit_posts_title_gin")
    op.execute("DROP INDEX IF EXISTS ix_research_sessions_query_gin")
    op.execute("DROP INDEX IF EXISTS ix_memories_content_gin")
