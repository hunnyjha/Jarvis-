"""Security investigation routes."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.security import InvestigationStatus, SecurityInvestigation
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.security import (
    InvestigateRequest,
    SecurityInvestigationDetail,
    SecurityInvestigationResponse,
)
from app.services.security_service import SecurityService

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _run_investigation(inv_id: uuid.UUID, target: str, inv_type: str) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = SecurityService(db)
        await service.run_investigation(inv_id, target, inv_type)


@router.post("/investigate", response_model=SecurityInvestigationResponse, status_code=status.HTTP_202_ACCEPTED)
async def investigate(
    payload: InvestigateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityInvestigation:
    """Start a security investigation."""
    title = payload.title or f"Investigation: {payload.target}"
    inv = SecurityInvestigation(
        user_id=current_user.id,
        title=title,
        target=payload.target,
        investigation_type=payload.investigation_type,
        status=InvestigationStatus.PENDING,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    background_tasks.add_task(_run_investigation, inv.id, payload.target, payload.investigation_type)
    logger.info("security.investigation.queued", inv_id=str(inv.id), target=payload.target)
    return inv


@router.get("/investigations", response_model=PaginatedResponse[SecurityInvestigationResponse])
async def list_investigations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SecurityInvestigationResponse]:
    total = await db.scalar(
        select(func.count(SecurityInvestigation.id)).where(
            SecurityInvestigation.user_id == current_user.id
        )
    )
    result = await db.execute(
        select(SecurityInvestigation)
        .where(SecurityInvestigation.user_id == current_user.id)
        .order_by(SecurityInvestigation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse.create(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.get("/investigations/{inv_id}", response_model=SecurityInvestigationDetail)
async def get_investigation(
    inv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecurityInvestigation:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(SecurityInvestigation)
        .options(selectinload(SecurityInvestigation.findings))
        .where(SecurityInvestigation.id == inv_id, SecurityInvestigation.user_id == current_user.id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return inv


@router.delete("/investigations/{inv_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_investigation(
    inv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(SecurityInvestigation).where(
            SecurityInvestigation.id == inv_id, SecurityInvestigation.user_id == current_user.id
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    await db.delete(inv)
    await db.commit()
