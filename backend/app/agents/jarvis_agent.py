"""
JARVIS Main Agent — LangGraph-based orchestrator that routes to specialist agents.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

logger = structlog.get_logger(__name__)


class JarvisAgent:
    """
    Main JARVIS conversational agent.
    Routes user messages to the appropriate specialist agent using Claude AI.
    """

    INTENT_PROMPT = """You are JARVIS, an AI Operating System for Reddit intelligence and research.

Classify the user's intent into one of these categories:
- reddit_analysis: Analyzing subreddits, Reddit posts, trends
- research: Web search, research queries, fact-finding
- security: OSINT, account investigations, threat analysis
- memory: Storing, retrieving, or searching memories
- report: Generating or viewing reports
- general: General conversation, help, or commands

Respond with JSON: {{"intent": "category", "confidence": 0.0-1.0, "extracted_params": {{}}}}"""

    def __init__(
        self, db: AsyncSession, redis: aioredis.Redis, user: User
    ) -> None:
        self.db = db
        self.redis = redis
        self.user = user

    async def chat(
        self,
        message: str,
        conversation_id: uuid.UUID,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process a user message and return a response."""
        import anthropic
        import json

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Classify intent
        intent_response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=200,
            system=self.INTENT_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        intent_text = intent_response.content[0].text
        try:
            start = intent_text.find("{")
            end = intent_text.rfind("}") + 1
            intent_data = json.loads(intent_text[start:end]) if start >= 0 else {}
            intent = intent_data.get("intent", "general")
        except Exception:
            intent = "general"

        # Retrieve relevant memories
        memories: List[str] = []
        try:
            from app.services.memory_service import MemoryService
            from app.schemas.memory import MemorySearchRequest
            svc = MemoryService(self.db)
            search_results = await svc.search(
                self.user.id,
                MemorySearchRequest(query=message, limit=3, min_relevance=0.6),
            )
            memories = [f"[Memory] {r.memory.title}: {r.memory.content[:200]}" for r in search_results]
        except Exception as e:
            logger.warning("Memory retrieval failed", error=str(e))

        # Build conversation context
        system_prompt = self._build_system_prompt(intent, memories)

        # Load conversation history from Redis
        history = await self._load_history(conversation_id)
        history.append({"role": "user", "content": message})

        # Generate response
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.AI_MAX_TOKENS,
            system=system_prompt,
            messages=history[-10:],  # Last 10 messages for context
        )

        assistant_message = response.content[0].text

        # Save updated history
        history.append({"role": "assistant", "content": assistant_message})
        await self._save_history(conversation_id, history)

        return {
            "message": assistant_message,
            "agent_used": intent,
            "tools_called": [],
            "memory_retrieved": len(memories),
        }

    def _build_system_prompt(self, intent: str, memories: List[str]) -> str:
        """Build a context-aware system prompt."""
        memory_context = "\n".join(memories) if memories else "No relevant memories found."

        base_prompt = f"""You are JARVIS, an advanced AI Operating System specializing in Reddit intelligence, research, and security analysis.

User: {self.user.username}
Current focus: {intent}

Relevant memories:
{memory_context}

Guidelines:
- Be direct, precise, and actionable
- For Reddit analysis: provide specific insights about subreddits and trends
- For research: synthesize information from multiple sources
- For security: be thorough but ethical (only analyze public data)
- For memory: help store and retrieve information effectively
- Always suggest follow-up actions the user can take in JARVIS"""

        return base_prompt

    async def _load_history(self, conversation_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Load conversation history from Redis."""
        import json
        key = f"conversation:{self.user.id}:{conversation_id}"
        raw = await self.redis.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return []
        return []

    async def _save_history(
        self, conversation_id: uuid.UUID, history: List[Dict[str, Any]]
    ) -> None:
        """Save conversation history to Redis."""
        import json
        key = f"conversation:{self.user.id}:{conversation_id}"
        # Keep last 20 messages
        await self.redis.setex(
            key,
            86400,  # 24 hour TTL
            json.dumps(history[-20:]),
        )
