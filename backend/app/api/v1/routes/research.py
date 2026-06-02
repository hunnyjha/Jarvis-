"""Research routes."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.research import ResearchSession, ResearchStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.research import (
    ResearchSessionDetail,
    ResearchSessionResponse,
    ResearchStartRequest,
)
from app.services.research_service import ResearchService

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _run_research(session_id: uuid.UUID, query: str, research_type: str) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = ResearchService(db)
        await service.run_session(session_id, query, research_type)


@router.post("/sessions", response_model=ResearchSessionResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_research(
    payload: ResearchStartRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchSession:
    """Start a new research session."""
    title = payload.title or payload.query[:100]
    session = ResearchSession(
        user_id=current_user.id,
        title=title,
        query=payload.query,
        research_type=payload.research_type,
        status=ResearchStatus.PENDING,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    background_tasks.add_task(_run_research, session.id, payload.query, payload.research_type)
    logger.info("research.session.queued", session_id=str(session.id))
    return session


@router.get("/sessions", response_model=PaginatedResponse[ResearchSessionResponse])
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ResearchSessionResponse]:
    total = await db.scalar(
        select(func.count(ResearchSession.id)).where(ResearchSession.user_id == current_user.id)
    )
    result = await db.execute(
        select(ResearchSession)
        .where(ResearchSession.user_id == current_user.id)
        .order_by(ResearchSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse.create(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.get("/sessions/{session_id}", response_model=ResearchSessionDetail)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchSession:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(ResearchSession)
        .options(selectinload(ResearchSession.results))
        .where(ResearchSession.id == session_id, ResearchSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ResearchSession).where(
            ResearchSession.id == session_id, ResearchSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)
    await db.commit()
