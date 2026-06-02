"""
Agent Service — bridges FastAPI routes to the JARVIS LangGraph graph.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = structlog.get_logger(__name__)

# In-memory task store (Redis-backed in production via task_runner)
_task_store: Dict[str, Dict[str, Any]] = {}


class AgentService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user

    async def chat(
        self,
        message: str,
        conversation_id: Optional[uuid.UUID],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run a full JARVIS graph execution for a chat message."""
        start_ms = int(time.time() * 1000)
        conv_id = conversation_id or uuid.uuid4()

        try:
            from app.agents.jarvis_agent import get_graph
            from app.agents.state import JarvisState

            initial_state: JarvisState = {
                "user_id": str(self.user.id),
                "conversation_id": str(conv_id),
                "messages": [{"role": "user", "content": message, "name": None, "tool_call_id": None}],
                "intent": None,
                "confidence": 0.0,
                "memories": [],
                "context": context or {},
                "agent_result": None,
                "tools_called": [],
                "error": None,
                "next_agent": None,
                "iterations": 0,
            }

            graph = get_graph()
            final_state = await graph.ainvoke(initial_state)

            result = final_state.get("agent_result", {})
            response_text = str(result.get("response", "I encountered an issue processing your request."))
            agent_used = result.get("agent", "orchestrator")
            tools_called = final_state.get("tools_called", [])

        except Exception as exc:
            logger.error("agent.chat_failed", error=str(exc), user_id=str(self.user.id))
            response_text = (
                "I encountered an error processing your request. "
                f"Error: {str(exc)[:200]}"
            )
            agent_used = "orchestrator"
            tools_called = []

        elapsed = int(time.time() * 1000) - start_ms
        return {
            "message": response_text,
            "conversation_id": conv_id,
            "agent_used": agent_used,
            "tools_called": tools_called,
            "memory_retrieved": 0,
            "processing_time_ms": elapsed,
        }

    async def dispatch_task(
        self, agent: str, task: str, params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a background agent task."""
        task_id = uuid.uuid4()
        now = datetime.utcnow()

        task_record = {
            "task_id": str(task_id),
            "agent": agent,
            "status": "queued",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        _task_store[str(task_id)] = task_record

        import asyncio
        asyncio.create_task(self._execute_task(str(task_id), agent, task, params or {}))

        return task_record

    async def _execute_task(
        self, task_id: str, agent: str, task: str, params: Dict[str, Any]
    ) -> None:
        record = _task_store.get(task_id)
        if not record:
            return
        try:
            record["status"] = "running"
            record["progress"] = 10
            record["updated_at"] = datetime.utcnow()

            # Dispatch through chat interface with forced intent
            context = {"forced_intent": agent, **params}
            result = await self.chat(task, None, context)
            record["result"] = result
            record["status"] = "completed"
            record["progress"] = 100

        except Exception as exc:
            logger.error("agent.task_failed", task_id=task_id, error=str(exc))
            record["status"] = "failed"
            record["error"] = str(exc)[:500]

        record["updated_at"] = datetime.utcnow()

    async def get_task_status(self, task_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        return _task_store.get(str(task_id))
