"""Agent and chat Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: UUID
    agent_used: str
    tools_called: List[str] = []
    memory_retrieved: int = 0
    processing_time_ms: int


class AgentTaskRequest(BaseModel):
    agent: str = Field(
        pattern=r"^(research|reddit|security|strategy|memory|report)$",
        description="Agent to invoke",
    )
    task: str = Field(min_length=1, max_length=5000)
    params: Optional[Dict[str, Any]] = None


class AgentTaskStatus(BaseModel):
    task_id: UUID
    agent: str
    status: str
    progress: int = Field(ge=0, le=100)
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
