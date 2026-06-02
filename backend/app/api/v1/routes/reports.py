"""
JARVIS Reports Routes — Generate, list, download, and delete reports.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.report import ReportDetail, ReportGenerateRequest, ReportResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


async def _generate_report(report_id: uuid.UUID, payload: ReportGenerateRequest) -> None:
    from app.core.database import get_session_factory
    from app.services.report_service import ReportService

    session_factory = get_session_factory()
    async with session_factory() as db:
        service = ReportService(db)
        await service.generate(report_id, payload)


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    payload: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Report:
    """Start async report generation. Poll GET /reports/{id} for completion."""
    report = Report(
        user_id=current_user.id,
        title=payload.title,
        report_type=payload.report_type,
        format=payload.format,
        source_id=payload.source_id,
        status=ReportStatus.GENERATING,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    background_tasks.add_task(_generate_report, report.id, payload)
    logger.info("report.generation.queued", report_id=str(report.id))
    return report


@router.get("/", response_model=PaginatedResponse[ReportResponse])
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ReportResponse]:
    """List all reports for the current user."""
    total = await db.scalar(
        select(func.count(Report.id)).where(Report.user_id == current_user.id)
    )
    result = await db.execute(
        select(Report)
        .where(Report.user_id == current_user.id)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse.create(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Report:
    """Get a report by ID including full content."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download a completed report file."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if report.status != ReportStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report is not yet completed")
    if not report.file_path or not Path(report.file_path).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found")

    # Increment download count
    report.file_size_bytes = report.file_size_bytes  # Touch to keep in session
    from sqlalchemy import update
    await db.execute(
        update(Report).where(Report.id == report_id).values(
            file_size_bytes=report.file_size_bytes
        )
    )
    await db.commit()

    ext_map = {"pdf": "application/pdf", "markdown": "text/markdown", "html": "text/html", "json": "application/json"}
    media_type = ext_map.get(str(report.format), "application/octet-stream")
    filename = f"jarvis_report_{report_id}.{report.format}"
    return FileResponse(path=report.file_path, media_type=media_type, filename=filename)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a report and its file."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    if report.file_path:
        try:
            Path(report.file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Failed to delete report file", error=str(e))

    await db.delete(report)
    await db.commit()
