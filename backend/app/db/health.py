"""Database health checks and diagnostics."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def check_database_health(db: AsyncSession) -> Dict[str, Any]:
    """Run comprehensive database health checks."""
    results: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }

    # Basic connectivity
    try:
        await db.execute(text("SELECT 1"))
        results["checks"]["connectivity"] = {"status": "ok"}
    except Exception as exc:
        results["checks"]["connectivity"] = {"status": "error", "detail": str(exc)}
        results["status"] = "unhealthy"

    # Check all tables exist
    expected_tables = [
        "users", "research_sessions", "research_results",
        "subreddit_analyses", "topic_discoveries", "reddit_posts",
        "security_investigations", "security_findings",
        "memory_collections", "memories", "reports", "audit_logs",
    ]
    try:
        result = await db.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
        )
        existing = {row[0] for row in result.fetchall()}
        missing = [t for t in expected_tables if t not in existing]
        results["checks"]["tables"] = {
            "status": "ok" if not missing else "warning",
            "found": len(existing),
            "missing": missing,
        }
    except Exception as exc:
        results["checks"]["tables"] = {"status": "error", "detail": str(exc)}

    # Check extensions
    try:
        result = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent')")
        )
        installed = [row[0] for row in result.fetchall()]
        results["checks"]["extensions"] = {
            "status": "ok" if len(installed) == 2 else "warning",
            "installed": installed,
        }
    except Exception as exc:
        results["checks"]["extensions"] = {"status": "error", "detail": str(exc)}

    # Row counts per table
    try:
        counts: Dict[str, int] = {}
        for table in expected_tables[:5]:  # Quick check on key tables
            count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = count_result.scalar() or 0
        results["checks"]["row_counts"] = {"status": "ok", "counts": counts}
    except Exception as exc:
        results["checks"]["row_counts"] = {"status": "error", "detail": str(exc)}

    # Check for any failed status with errors (aggregate)
    has_error = any(
        v.get("status") == "error" for v in results["checks"].values()
    )
    if has_error:
        results["status"] = "unhealthy"

    return results


async def get_table_stats(db: AsyncSession) -> List[Dict[str, Any]]:
    """Return table size statistics for monitoring."""
    try:
        result = await db.execute(text("""
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS index_size,
                n_live_tup AS row_count
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """))
        return [
            {
                "table": row[1],
                "total_size": row[2],
                "table_size": row[3],
                "index_size": row[4],
                "row_count": row[5],
            }
            for row in result.fetchall()
        ]
    except Exception as exc:
        logger.warning("db.stats_failed", error=str(exc))
        return []
