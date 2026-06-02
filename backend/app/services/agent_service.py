"""Agent Orchestration Service — routes user intent to the right agents."""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.schemas.memory import MemorySearchRequest

logger = structlog.get_logger(__name__)

# In-memory task store (production would use Redis)
_task_store: Dict[str, Dict[str, Any]] = {}


class AgentService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.ai = AIService()
        self.memory_service = MemoryService(db)

    async def chat(
        self,
        message: str,
        conversation_id: Optional[uuid.UUID],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Main chat handler — retrieves memories, calls AI, stores response."""
        start_ms = int(time.time() * 1000)
        conv_id = conversation_id or uuid.uuid4()

        # Retrieve relevant memories
        memories: List[str] = []
        try:
            search_results = await self.memory_service.search(
                self.user.id,
                MemorySearchRequest(query=message, limit=5),
            )
            memories = [f"{r.memory.title}: {r.memory.content[:200]}" for r in search_results]
        except Exception as exc:
            logger.warning("agent.memory_retrieval_failed", error=str(exc))

        # Generate response
        ai_result = await self.ai.chat_response(message, context, memories)

        elapsed = int(time.time() * 1000) - start_ms

        return {
            "message": ai_result.get("message", ""),
            "conversation_id": conv_id,
            "agent_used": ai_result.get("agent_used", "orchestrator"),
            "tools_called": ai_result.get("tools_called", []),
            "memory_retrieved": len(memories),
            "processing_time_ms": elapsed,
        }

    async def dispatch_task(
        self, agent: str, task: str, params: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create and queue an agent task."""
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

        # Dispatch to the right service based on agent type
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

            if agent == "research":
                from app.services.research_service import ResearchService
                from app.models.research import ResearchSession, ResearchStatus
                session = ResearchSession(
                    user_id=self.user.id,
                    title=task[:100],
                    query=task,
                    research_type="web_search",
                    status=ResearchStatus.PENDING,
                )
                self.db.add(session)
                await self.db.commit()
                await self.db.refresh(session)
                svc = ResearchService(self.db)
                await svc.run_session(session.id, task, "web_search")
                record["result"] = {"session_id": str(session.id)}

            elif agent == "strategy":
                options = params.get("options", ["Option A", "Option B", "Option C"])
                result = await self.ai.generate_strategy(task, options)
                record["result"] = result

            else:
                result = await self.ai.chat_response(task, params, [])
                record["result"] = {"response": result.get("message")}

            record["status"] = "completed"
            record["progress"] = 100

        except Exception as exc:
            logger.error("agent.task_failed", task_id=task_id, error=str(exc))
            record["status"] = "failed"
            record["error"] = str(exc)

        record["updated_at"] = datetime.utcnow()

    async def get_task_status(self, task_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        return _task_store.get(str(task_id))
