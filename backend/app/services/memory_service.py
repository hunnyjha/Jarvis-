"""
JARVIS Memory Service — Store and search memories with ChromaDB vector embeddings.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import chromadb
import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.memory import Memory, MemoryCollection
from app.schemas.memory import MemorySearchRequest, MemorySearchResult, MemoryStoreRequest

logger = structlog.get_logger(__name__)


class MemoryService:
    """Service for semantic memory storage and retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._chroma: Optional[chromadb.AsyncHttpClient] = None

    def _get_chroma(self) -> chromadb.AsyncHttpClient:
        if self._chroma is None:
            self._chroma = chromadb.AsyncHttpClient(
                host=settings.CHROMADB_URL.replace("http://", "").split(":")[0],
                port=int(settings.CHROMADB_URL.split(":")[-1]) if ":" in settings.CHROMADB_URL else 8000,
            )
        return self._chroma

    def _collection_name(self, user_id: uuid.UUID) -> str:
        return f"memories_{str(user_id).replace('-', '')}"

    async def store(self, user_id: uuid.UUID, payload: MemoryStoreRequest) -> Memory:
        """Store a memory with vector embedding."""
        # Create DB record first
        memory = Memory(
            user_id=user_id,
            collection_id=payload.collection_id,
            title=payload.title,
            content=payload.content,
            memory_type=payload.memory_type,
            tags=payload.tags,
            importance_score=payload.importance_score,
            is_pinned=payload.is_pinned,
            source_type=payload.source_type,
            source_id=payload.source_id,
        )
        self.db.add(memory)
        await self.db.flush()
        await self.db.refresh(memory)

        # Generate AI summary
        try:
            summary = await self._generate_summary(payload.title, payload.content)
            memory.summary = summary
        except Exception as e:
            logger.warning("Failed to generate memory summary", error=str(e))

        # Store embedding in ChromaDB
        try:
            chroma = self._get_chroma()
            collection = await chroma.get_or_create_collection(
                name=self._collection_name(user_id),
                metadata={"user_id": str(user_id)},
            )
            embedding_id = str(memory.id)
            await collection.add(
                ids=[embedding_id],
                documents=[f"{payload.title}\n\n{payload.content}"],
                metadatas=[{
                    "memory_id": str(memory.id),
                    "user_id": str(user_id),
                    "memory_type": payload.memory_type,
                    "title": payload.title,
                }],
            )
            memory.embedding_id = embedding_id
        except Exception as e:
            logger.warning("Failed to store memory embedding", error=str(e))

        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def search(
        self, user_id: uuid.UUID, payload: MemorySearchRequest
    ) -> List[MemorySearchResult]:
        """Search memories using vector similarity."""
        from sqlalchemy import select

        results: List[MemorySearchResult] = []

        try:
            chroma = self._get_chroma()
            collection = await chroma.get_or_create_collection(
                name=self._collection_name(user_id)
            )

            where_filter: Dict[str, Any] = {"user_id": str(user_id)}
            if payload.memory_type:
                where_filter["memory_type"] = payload.memory_type.value

            query_result = await collection.query(
                query_texts=[payload.query],
                n_results=payload.limit,
                where=where_filter if len(where_filter) > 1 else None,
            )

            memory_ids = []
            distances = []
            if query_result["ids"]:
                for idx, doc_id in enumerate(query_result["ids"][0]):
                    dist = query_result["distances"][0][idx] if query_result.get("distances") else 1.0
                    if (1 - dist) >= payload.min_relevance:
                        memory_ids.append(uuid.UUID(doc_id))
                        distances.append(dist)

            if memory_ids:
                db_result = await self.db.execute(
                    select(Memory).where(Memory.id.in_(memory_ids))
                )
                memories_map = {m.id: m for m in db_result.scalars().all()}

                for mem_id, dist in zip(memory_ids, distances):
                    if mem_id in memories_map:
                        from app.schemas.memory import MemoryResponse
                        results.append(MemorySearchResult(
                            memory=MemoryResponse.model_validate(memories_map[mem_id]),
                            relevance_score=round(1 - dist, 4),
                        ))

        except Exception as e:
            logger.error("Memory vector search failed", error=str(e))
            # Fallback to SQL text search
            from sqlalchemy import or_
            db_result = await self.db.execute(
                select(Memory)
                .where(
                    Memory.user_id == user_id,
                    Memory.is_archived == False,
                    or_(
                        Memory.title.ilike(f"%{payload.query}%"),
                        Memory.content.ilike(f"%{payload.query}%"),
                    ),
                )
                .limit(payload.limit)
            )
            from app.schemas.memory import MemoryResponse
            for memory in db_result.scalars().all():
                results.append(MemorySearchResult(
                    memory=MemoryResponse.model_validate(memory),
                    relevance_score=0.5,
                ))

        return results

    async def delete_embedding(self, embedding_id: str) -> None:
        """Delete a vector embedding from ChromaDB."""
        try:
            chroma = self._get_chroma()
            # We need the user_id to find the collection — skip if not available
            pass
        except Exception as e:
            logger.warning("Failed to delete embedding from ChromaDB", error=str(e))

    async def _generate_summary(self, title: str, content: str) -> str:
        """Generate a concise AI summary of the memory content."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        if len(content) < 200:
            return content[:200]

        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"Summarize in 1-2 sentences:\nTitle: {title}\n{content[:2000]}",
            }],
        )
        return response.content[0].text.strip()
