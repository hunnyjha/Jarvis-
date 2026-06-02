"""Dashboard routes — stats, activity feed, quick summaries."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.memory import Memory
from app.models.reddit import SubredditAnalysis
from app.models.report import Report
from app.models.research import ResearchSession
from app.models.security import SecurityInvestigation
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return dashboard statistics for the authenticated user."""
    user_id = current_user.id

    research_count = await db.scalar(
        select(func.count(ResearchSession.id)).where(ResearchSession.user_id == user_id)
    )
    reddit_count = await db.scalar(
        select(func.count(SubredditAnalysis.id)).where(SubredditAnalysis.user_id == user_id)
    )
    security_count = await db.scalar(
        select(func.count(SecurityInvestigation.id)).where(
            SecurityInvestigation.user_id == user_id
        )
    )
    memory_count = await db.scalar(
        select(func.count(Memory.id)).where(
            Memory.user_id == user_id, Memory.is_archived == False
        )
    )
    report_count = await db.scalar(
        select(func.count(Report.id)).where(Report.user_id == user_id)
    )

    return {
        "research_sessions": research_count or 0,
        "subreddit_analyses": reddit_count or 0,
        "security_investigations": security_count or 0,
        "memories": memory_count or 0,
        "reports": report_count or 0,
    }


@router.get("/recent-reports")
async def get_recent_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return 5 most recent reports."""
    result = await db.execute(
        select(Report)
        .where(Report.user_id == current_user.id)
        .order_by(Report.created_at.desc())
        .limit(5)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "report_type": r.report_type,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.get("/activity")
async def get_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return recent activity across all modules."""
    activities: List[Dict[str, Any]] = []

    # Recent research
    research_result = await db.execute(
        select(ResearchSession)
        .where(ResearchSession.user_id == current_user.id)
        .order_by(ResearchSession.created_at.desc())
        .limit(3)
    )
    for r in research_result.scalars().all():
        activities.append({
            "type": "research",
            "id": str(r.id),
            "title": r.title,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        })

    # Recent subreddit analyses
    reddit_result = await db.execute(
        select(SubredditAnalysis)
        .where(SubredditAnalysis.user_id == current_user.id)
        .order_by(SubredditAnalysis.created_at.desc())
        .limit(3)
    )
    for r in reddit_result.scalars().all():
        activities.append({
            "type": "reddit_analysis",
            "id": str(r.id),
            "title": f"r/{r.subreddit_name}",
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        })

    # Sort combined by created_at
    activities.sort(key=lambda x: x["created_at"], reverse=True)
    return activities[:10]
