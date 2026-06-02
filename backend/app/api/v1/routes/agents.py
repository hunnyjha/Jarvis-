"""
JARVIS Agent Routes — Main JARVIS chat interface and agent task management.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.agent import (
    AgentTaskRequest,
    AgentTaskStatus,
    ChatRequest,
    ChatResponse,
)

import redis.asyncio as aioredis

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> ChatResponse:
    """
    Main JARVIS conversational interface.
    Routes to the appropriate specialist agent based on intent.
    """
    import time
    from app.agents.jarvis_agent import JarvisAgent

    start = time.perf_counter()
    agent = JarvisAgent(db=db, redis=redis, user=current_user)

    conversation_id = payload.conversation_id or uuid.uuid4()
    result = await agent.chat(
        message=payload.message,
        conversation_id=conversation_id,
        context=payload.context or {},
    )

    processing_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "agent.chat.completed",
        user_id=str(current_user.id),
        conversation_id=str(conversation_id),
        agent_used=result.get("agent_used", "jarvis"),
        processing_ms=processing_ms,
    )

    return ChatResponse(
        message=result["message"],
        conversation_id=conversation_id,
        agent_used=result.get("agent_used", "jarvis"),
        tools_called=result.get("tools_called", []),
        memory_retrieved=result.get("memory_retrieved", 0),
        processing_time_ms=processing_ms,
    )


@router.post("/task", response_model=AgentTaskStatus, status_code=status.HTTP_202_ACCEPTED)
async def run_task(
    payload: AgentTaskRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> AgentTaskStatus:
    """
    Run a specific agent task asynchronously.
    Returns a task ID — poll GET /agents/tasks/{id}/status for results.
    """
    task_id = uuid.uuid4()
    now = datetime.utcnow()

    initial_status = AgentTaskStatus(
        task_id=task_id,
        agent=payload.agent,
        status="pending",
        progress=0,
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )

    # Store initial status in Redis
    import json
    await redis.setex(
        f"task:{task_id}",
        3600,  # 1 hour TTL
        json.dumps(initial_status.model_dump(), default=str),
    )

    async def _run_agent_task(task_id: uuid.UUID, payload: AgentTaskRequest, user_id: str) -> None:
        import json
        from app.agents.task_runner import run_agent_task
        from app.core.redis import get_redis_client

        r = get_redis_client()
        try:
            await r.setex(
                f"task:{task_id}",
                3600,
                json.dumps({"task_id": str(task_id), "agent": payload.agent, "status": "running", "progress": 10,
                            "result": None, "error": None, "created_at": str(now), "updated_at": str(datetime.utcnow())})
            )
            result = await run_agent_task(agent=payload.agent, task=payload.task, params=payload.params or {}, user_id=user_id)
            await r.setex(
                f"task:{task_id}",
                3600,
                json.dumps({"task_id": str(task_id), "agent": payload.agent, "status": "completed", "progress": 100,
                            "result": result, "error": None, "created_at": str(now), "updated_at": str(datetime.utcnow())})
            )
        except Exception as exc:
            await r.setex(
                f"task:{task_id}",
                3600,
                json.dumps({"task_id": str(task_id), "agent": payload.agent, "status": "failed", "progress": 0,
                            "result": None, "error": str(exc), "created_at": str(now), "updated_at": str(datetime.utcnow())})
            )

    background_tasks.add_task(_run_agent_task, task_id, payload, str(current_user.id))
    logger.info("agent.task.queued", task_id=str(task_id), agent=payload.agent)
    return initial_status


@router.get("/tasks/{task_id}/status", response_model=AgentTaskStatus)
async def get_task_status(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> AgentTaskStatus:
    """Get the status of a running or completed agent task."""
    import json

    raw = await redis.get(f"task:{task_id}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or expired")

    data = json.loads(raw)
    return AgentTaskStatus(**data)


@router.get("/history")
async def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> List[Dict[str, Any]]:
    """Get recent conversation history for the current user."""
    import json

    keys = await redis.keys(f"conversation:{current_user.id}:*")
    conversations = []
    for key in keys[:limit]:
        raw = await redis.get(key)
        if raw:
            try:
                conversations.append(json.loads(raw))
            except json.JSONDecodeError:
                continue

    return sorted(conversations, key=lambda x: x.get("updated_at", ""), reverse=True)[:limit]
