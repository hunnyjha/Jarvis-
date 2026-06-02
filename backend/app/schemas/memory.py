"""Memory Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.memory import MemoryType


class MemoryCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = None


class MemoryCollectionResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryStoreRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    memory_type: MemoryType = MemoryType.NOTE
    collection_id: Optional[UUID] = None
    tags: Optional[List[str]] = None
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_pinned: bool = False
    source_type: Optional[str] = None
    source_id: Optional[str] = None


class MemoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    collection_id: Optional[UUID]
    title: str
    content: str
    summary: Optional[str]
    memory_type: MemoryType
    tags: Optional[List[str]]
    importance_score: float
    access_count: int
    is_pinned: bool
    is_archived: bool
    source_type: Optional[str]
    source_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    collection_id: Optional[UUID] = None
    memory_type: Optional[MemoryType] = None
    limit: int = Field(default=10, ge=1, le=50)
    min_relevance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemorySearchResult(BaseModel):
    memory: MemoryResponse
    relevance_score: float
