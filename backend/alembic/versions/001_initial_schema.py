"""Initial schema — all JARVIS tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE research_type_enum AS ENUM (
                'web_search', 'reddit_analysis', 'multi_source', 'deep_dive', 'competitive'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE research_status_enum AS ENUM (
                'pending', 'in_progress', 'completed', 'failed', 'cancelled'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE analysis_status_enum AS ENUM (
                'pending', 'in_progress', 'completed', 'failed'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sentiment_label_enum AS ENUM (
                'very_positive', 'positive', 'neutral', 'negative', 'very_negative', 'mixed'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE investigation_status_enum AS ENUM (
                'pending', 'in_progress', 'completed', 'failed'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE investigation_type_enum AS ENUM (
                'account_scan', 'identity_search', 'threat_assessment', 'osint_collection', 'background_check'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE severity_level_enum AS ENUM (
                'critical', 'high', 'medium', 'low', 'info'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE finding_type_enum AS ENUM (
                'personal_info', 'social_presence', 'behavioral_pattern', 
                'risk_indicator', 'timeline_event', 'association', 'anomaly'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE memory_type_enum AS ENUM (
                'conversation', 'research', 'subreddit_report', 'competitor_report',
                'growth_experiment', 'decision', 'preference', 'insight', 'fact', 'note'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE report_type_enum AS ENUM (
                'subreddit_analysis', 'topic_discovery', 'security_investigation',
                'research_session', 'competitor_analysis', 'growth_strategy', 'custom'
            );
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE report_format_enum AS ENUM ('pdf', 'markdown', 'html', 'json');
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE report_status_enum AS ENUM ('generating', 'completed', 'failed');
            EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── users ────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
        comment="User accounts and authentication",
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ── research_sessions ────────────────────────────────────────
    op.create_table(
        "research_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("research_type", sa.Enum("research_type_enum", create_type=False), nullable=False, server_default="web_search"),
        sa.Column("status", sa.Enum("research_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("sources_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="User-initiated research sessions",
    )
    op.create_index("ix_research_sessions_user_id", "research_sessions", ["user_id"])
    op.create_index("ix_research_sessions_status", "research_sessions", ["status"])
    op.create_index("ix_research_sessions_created_at", "research_sessions", ["created_at"])

    # ── research_results ─────────────────────────────────────────
    op.create_table(
        "research_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("snippet", sa.Text, nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("analysis", postgresql.JSONB, nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["research_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Individual research results within a session",
    )
    op.create_index("ix_research_results_session_id", "research_results", ["session_id"])

    # ── subreddit_analyses ───────────────────────────────────────
    op.create_table(
        "subreddit_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subreddit_name", sa.String(100), nullable=False),
        sa.Column("status", sa.Enum("analysis_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("subscriber_count", sa.Integer, nullable=True),
        sa.Column("active_users", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_utc", sa.Float, nullable=True),
        sa.Column("time_period", sa.String(20), nullable=False, server_default="week"),
        sa.Column("post_limit", sa.Integer, nullable=False, server_default="100"),
        sa.Column("posts_analyzed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_sentiment", sa.Enum("sentiment_label_enum", create_type=False), nullable=True),
        sa.Column("sentiment_scores", postgresql.JSONB, nullable=True),
        sa.Column("top_topics", postgresql.JSONB, nullable=True),
        sa.Column("trending_keywords", postgresql.JSONB, nullable=True),
        sa.Column("avg_score", sa.Float, nullable=True),
        sa.Column("avg_comments", sa.Float, nullable=True),
        sa.Column("engagement_rate", sa.Float, nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("key_insights", postgresql.JSONB, nullable=True),
        sa.Column("opportunities", postgresql.JSONB, nullable=True),
        sa.Column("raw_analysis", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Subreddit analysis results",
    )
    op.create_index("ix_subreddit_analyses_user_id", "subreddit_analyses", ["user_id"])
    op.create_index("ix_subreddit_analyses_subreddit_name", "subreddit_analyses", ["subreddit_name"])
    op.create_index("ix_subreddit_analyses_status", "subreddit_analyses", ["status"])

    # ── topic_discoveries ────────────────────────────────────────
    op.create_table(
        "topic_discoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_name", sa.String(255), nullable=False),
        sa.Column("topic_description", sa.Text, nullable=True),
        sa.Column("frequency", sa.Integer, nullable=False, server_default="0"),
        sa.Column("relevance_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("sentiment", sa.Enum("sentiment_label_enum", create_type=False), nullable=True),
        sa.Column("related_posts_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("keywords", postgresql.JSONB, nullable=True),
        sa.Column("examples", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["analysis_id"], ["subreddit_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Topics discovered within subreddit analyses",
    )
    op.create_index("ix_topic_discoveries_analysis_id", "topic_discoveries", ["analysis_id"])

    # ── reddit_posts ─────────────────────────────────────────────
    op.create_table(
        "reddit_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reddit_id", sa.String(20), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("author", sa.String(100), nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("permalink", sa.Text, nullable=True),
        sa.Column("selftext", sa.Text, nullable=True),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("upvote_ratio", sa.Float, nullable=True),
        sa.Column("num_comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_self", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("flair", sa.String(100), nullable=True),
        sa.Column("created_utc", sa.Float, nullable=True),
        sa.Column("sentiment", sa.Enum("sentiment_label_enum", create_type=False), nullable=True),
        sa.Column("ai_analysis", postgresql.JSONB, nullable=True),
        sa.Column("top_comments", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["analysis_id"], ["subreddit_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Reddit posts collected during analysis",
    )
    op.create_index("ix_reddit_posts_analysis_id", "reddit_posts", ["analysis_id"])
    op.create_index("ix_reddit_posts_reddit_id", "reddit_posts", ["reddit_id"])

    # ── security_investigations ──────────────────────────────────
    op.create_table(
        "security_investigations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target", sa.String(500), nullable=False),
        sa.Column("investigation_type", sa.Enum("investigation_type_enum", create_type=False), nullable=False, server_default="account_scan"),
        sa.Column("status", sa.Enum("investigation_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("findings_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Float, nullable=True),
        sa.Column("risk_level", sa.Enum("severity_level_enum", create_type=False), nullable=True),
        sa.Column("executive_summary", sa.Text, nullable=True),
        sa.Column("recommendations", postgresql.JSONB, nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Security and OSINT investigations",
    )
    op.create_index("ix_security_investigations_user_id", "security_investigations", ["user_id"])
    op.create_index("ix_security_investigations_status", "security_investigations", ["status"])

    # ── security_findings ────────────────────────────────────────
    op.create_table(
        "security_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("finding_type", sa.Enum("finding_type_enum", create_type=False), nullable=False),
        sa.Column("severity", sa.Enum("severity_level_enum", create_type=False), nullable=False, server_default="info"),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("evidence", postgresql.JSONB, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["investigation_id"], ["security_investigations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Individual findings within a security investigation",
    )
    op.create_index("ix_security_findings_investigation_id", "security_findings", ["investigation_id"])
    op.create_index("ix_security_findings_severity", "security_findings", ["severity"])

    # ── memory_collections ───────────────────────────────────────
    op.create_table(
        "memory_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("chroma_collection_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Named collections for organizing memories",
    )
    op.create_index("ix_memory_collections_user_id", "memory_collections", ["user_id"])

    # ── memories ─────────────────────────────────────────────────
    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("memory_type", sa.Enum("memory_type_enum", create_type=False), nullable=False, server_default="note"),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("importance_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source_type", sa.String(100), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["memory_collections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Long-term semantic memory entries",
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_collection_id", "memories", ["collection_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_is_pinned", "memories", ["is_pinned"])
    op.create_index("ix_memories_created_at", "memories", ["created_at"])

    # ── reports ──────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("report_type", sa.Enum("report_type_enum", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("report_status_enum", create_type=False), nullable=False, server_default="generating"),
        sa.Column("executive_summary", sa.Text, nullable=True),
        sa.Column("content", postgresql.JSONB, nullable=True),
        sa.Column("format", sa.Enum("report_format_enum", create_type=False), nullable=False, server_default="markdown"),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("share_token", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
        comment="Generated analysis reports",
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_reports_report_type", "reports", ["report_type"])
    op.create_index("ix_reports_status", "reports", ["status"])

    # ── audit_logs ───────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("extra_data", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Immutable audit log for all user actions",
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("reports")
    op.drop_table("memories")
    op.drop_table("memory_collections")
    op.drop_table("security_findings")
    op.drop_table("security_investigations")
    op.drop_table("reddit_posts")
    op.drop_table("topic_discoveries")
    op.drop_table("subreddit_analyses")
    op.drop_table("research_results")
    op.drop_table("research_sessions")
    op.drop_table("users")

    # Drop enums
    for enum_name in [
        "report_status_enum", "report_format_enum", "report_type_enum",
        "memory_type_enum", "finding_type_enum", "severity_level_enum",
        "investigation_type_enum", "investigation_status_enum",
        "sentiment_label_enum", "analysis_status_enum",
        "research_status_enum", "research_type_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
