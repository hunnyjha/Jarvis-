"""Security investigation Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.security import (
    FindingType,
    InvestigationStatus,
    InvestigationType,
    SeverityLevel,
)


class InvestigateRequest(BaseModel):
    target: str = Field(min_length=1, max_length=500)
    title: Optional[str] = None
    investigation_type: InvestigationType = InvestigationType.ACCOUNT_SCAN
    notes: Optional[str] = None


class SecurityFindingSchema(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    finding_type: FindingType
    severity: SeverityLevel
    source: Optional[str]
    source_url: Optional[str]
    evidence: Optional[Dict[str, Any]]
    confidence_score: Optional[float]
    is_verified: bool
    tags: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class SecurityInvestigationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    target: str
    investigation_type: InvestigationType
    status: InvestigationStatus
    findings_count: int
    risk_score: Optional[float]
    risk_level: Optional[SeverityLevel]
    executive_summary: Optional[str]
    recommendations: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SecurityInvestigationDetail(SecurityInvestigationResponse):
    findings: List[SecurityFindingSchema] = []
