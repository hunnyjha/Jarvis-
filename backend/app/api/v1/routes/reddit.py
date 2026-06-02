"""Reddit intelligence routes."""
from __future__ import annotations

import uuid
from typing import List

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.reddit import AnalysisStatus, SubredditAnalysis
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.reddit import (
    SubredditAnalyzeRequest,
    SubredditAnalysisDetail,
    SubredditAnalysisResponse,
    TopicDiscoverRequest,
)
from app.services.reddit_service import RedditService

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _run_analysis(analysis_id: uuid.UUID, request: SubredditAnalyzeRequest) -> None:
    """Background task that runs the subreddit analysis."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = RedditService(db)
        await service.run_analysis(analysis_id, request)


@router.post("/analyze", response_model=SubredditAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_subreddit(
    payload: SubredditAnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubredditAnalysis:
    """Kick off a subreddit analysis. Returns immediately; processing runs in background."""
    analysis = SubredditAnalysis(
        user_id=current_user.id,
        subreddit_name=payload.subreddit_name.strip().lstrip("r/"),
        time_period=payload.time_period,
        post_limit=payload.post_limit,
        status=AnalysisStatus.PENDING,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    background_tasks.add_task(_run_analysis, analysis.id, payload)
    logger.info("reddit.analysis.queued", analysis_id=str(analysis.id), subreddit=payload.subreddit_name)
    return analysis


@router.get("/analyses", response_model=PaginatedResponse[SubredditAnalysisResponse])
async def list_analyses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SubredditAnalysisResponse]:
    """List all subreddit analyses for the current user."""
    from sqlalchemy import func

    total = await db.scalar(
        select(func.count(SubredditAnalysis.id)).where(SubredditAnalysis.user_id == current_user.id)
    )
    result = await db.execute(
        select(SubredditAnalysis)
        .where(SubredditAnalysis.user_id == current_user.id)
        .order_by(SubredditAnalysis.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse.create(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.get("/analyses/{analysis_id}", response_model=SubredditAnalysisDetail)
async def get_analysis(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubredditAnalysis:
    """Get detailed analysis including posts and topics."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(SubredditAnalysis)
        .options(selectinload(SubredditAnalysis.posts), selectinload(SubredditAnalysis.topics))
        .where(SubredditAnalysis.id == analysis_id, SubredditAnalysis.user_id == current_user.id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a subreddit analysis."""
    result = await db.execute(
        select(SubredditAnalysis).where(
            SubredditAnalysis.id == analysis_id, SubredditAnalysis.user_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    await db.delete(analysis)
    await db.commit()
