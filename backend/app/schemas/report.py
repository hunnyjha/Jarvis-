"""Report Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.report import ReportFormat, ReportStatus, ReportType


class ReportGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    report_type: ReportType
    source_id: str = Field(description="ID of the source entity to report on")
    format: ReportFormat = ReportFormat.MARKDOWN
    include_raw_data: bool = False


class ReportResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    report_type: ReportType
    status: ReportStatus
    format: ReportFormat
    executive_summary: Optional[str]
    file_path: Optional[str]
    file_size_bytes: Optional[int]
    source_id: Optional[str]
    is_public: bool
    share_token: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportDetail(ReportResponse):
    content: Optional[Dict[str, Any]]
