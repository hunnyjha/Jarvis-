"""Research Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.research import ResearchStatus, ResearchType


class ResearchStartRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    research_type: ResearchType = ResearchType.WEB_SEARCH
    title: Optional[str] = None


class ResearchResultSchema(BaseModel):
    id: UUID
    title: str
    url: Optional[str]
    source: Optional[str]
    snippet: Optional[str]
    relevance_score: Optional[float]
    analysis: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    query: str
    research_type: ResearchType
    status: ResearchStatus
    summary: Optional[str]
    sources_count: int
    metadata: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchSessionDetail(ResearchSessionResponse):
    results: List[ResearchResultSchema] = []


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    max_results: int = Field(default=10, ge=1, le=50)
    include_reddit: bool = True
