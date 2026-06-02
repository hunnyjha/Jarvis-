"""Research Service — multi-source research orchestration."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.research import ResearchResult, ResearchSession, ResearchStatus
from app.services.ai_service import AIService

logger = structlog.get_logger(__name__)


class ResearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai = AIService()

    async def run_session(self, session_id: uuid.UUID, query: str, research_type: str) -> None:
        result = await self.db.execute(select(ResearchSession).where(ResearchSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return

        try:
            session.status = ResearchStatus.IN_PROGRESS
            await self.db.commit()

            # Gather sources
            sources: List[Dict[str, Any]] = []
            sources.extend(await self._search_reddit(query))

            # AI synthesis
            ai_result = await self.ai.research_query(query, sources)

            # Store results
            for src in sources:
                research_result = ResearchResult(
                    session_id=session_id,
                    title=src.get("title", "Untitled"),
                    url=src.get("url"),
                    source=src.get("source"),
                    content=src.get("content", "")[:10000],
                    snippet=src.get("snippet", "")[:500],
                    relevance_score=src.get("relevance_score", 0.5),
                )
                self.db.add(research_result)

            session.summary = ai_result.get("summary", "")
            session.sources_count = len(sources)
            session.extra_metadata = ai_result
            session.status = ResearchStatus.COMPLETED
            await self.db.commit()
            logger.info("research.session.completed", session_id=str(session_id))

        except Exception as exc:
            logger.error("research.session.failed", session_id=str(session_id), error=str(exc))
            session.status = ResearchStatus.FAILED
            session.error_message = str(exc)[:1000]
            await self.db.commit()

    async def _search_reddit(self, query: str) -> List[Dict[str, Any]]:
        """Search Reddit via PRAW for research sources."""
        import asyncio
        import praw

        def _sync_search():
            reddit = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT,
            )
            results = []
            for sub in reddit.subreddit("all").search(query, limit=10, sort="relevance"):
                results.append({
                    "title": sub.title,
                    "url": f"https://reddit.com{sub.permalink}",
                    "source": f"r/{sub.subreddit.display_name}",
                    "content": sub.selftext[:2000] if sub.selftext else "",
                    "snippet": (sub.selftext[:200] + "...") if sub.selftext else sub.title,
                    "relevance_score": min(1.0, sub.score / 1000),
                })
            return results

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _sync_search)
        except Exception as exc:
            logger.warning("research.reddit_search_failed", error=str(exc))
            return []
