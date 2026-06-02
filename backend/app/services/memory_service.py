"""
Memory Service — ChromaDB vector storage + PostgreSQL metadata + importance scoring.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.memory import Memory, MemoryCollection, MemoryType
from app.schemas.memory import (
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryStoreRequest,
)

logger = structlog.get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"


def _chroma_client():
    import chromadb
    host, port = settings.CHROMADB_URL.replace("http://", "").replace("https://", "").split(":")
    return chromadb.HttpClient(host=host, port=int(port))


class MemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─── Storage ─────────────────────────────────────────────────

    async def store(self, user_id: uuid.UUID, payload: MemoryStoreRequest) -> Memory:
        """Store memory in PostgreSQL and embed in ChromaDB."""
        memory = Memory(
            user_id=user_id,
            title=payload.title,
            content=payload.content,
            memory_type=payload.memory_type,
            collection_id=payload.collection_id,
            tags=payload.tags,
            importance_score=payload.importance_score,
            is_pinned=payload.is_pinned,
            source_type=payload.source_type,
            source_id=payload.source_id,
        )
        self.db.add(memory)
        await self.db.flush()

        # Embed in ChromaDB
        embedding_id = await self._embed_memory(memory)
        if embedding_id:
            memory.embedding_id = embedding_id
            memory.embedding_model = EMBEDDING_MODEL

        await self.db.commit()
        await self.db.refresh(memory)
        logger.info("memory.stored", memory_id=str(memory.id), type=payload.memory_type)
        return memory

    async def auto_store(
        self,
        user_id: uuid.UUID,
        title: str,
        content: str,
        memory_type: MemoryType = MemoryType.NOTE,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        importance: float = 0.5,
    ) -> Memory:
        """Convenience method for auto-storing memories from agent runs."""
        payload = MemoryStoreRequest(
            title=title,
            content=content,
            memory_type=memory_type,
            source_type=source_type,
            source_id=source_id,
            importance_score=importance,
        )
        return await self.store(user_id, payload)

    # ─── Search ───────────────────────────────────────────────────

    async def search(
        self, user_id: uuid.UUID, payload: MemorySearchRequest
    ) -> List[MemorySearchResult]:
        """Semantic vector search, with SQL full-text fallback."""
        results = await self._vector_search(user_id, payload)
        if not results:
            results = await self._fulltext_search(user_id, payload)
        return results

    async def get_context_memories(
        self, user_id: uuid.UUID, query: str, limit: int = 5
    ) -> List[str]:
        """Return memory snippets for injecting into agent context."""
        results = await self.search(
            user_id,
            MemorySearchRequest(query=query, limit=limit, min_relevance=0.4),
        )
        return [
            f"[{r.memory.memory_type.upper()}] {r.memory.title}: {r.memory.content[:300]}"
            for r in results
        ]

    async def _vector_search(
        self, user_id: uuid.UUID, payload: MemorySearchRequest
    ) -> List[MemorySearchResult]:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                self._chroma_query_sync,
                payload.query,
                str(user_id),
                payload.limit,
                str(payload.collection_id) if payload.collection_id else None,
            )
        except Exception as exc:
            logger.warning("memory.vector_search_failed", error=str(exc))
            return []

        results: List[MemorySearchResult] = []
        for item in raw:
            score = item.get("score", 0.0)
            if score < payload.min_relevance:
                continue
            try:
                mem_id = uuid.UUID(item["id"])
            except (ValueError, KeyError):
                continue
            db_result = await self.db.execute(
                select(Memory).where(Memory.id == mem_id, Memory.user_id == user_id)
            )
            memory = db_result.scalar_one_or_none()
            if memory and not memory.is_archived:
                memory.access_count += 1
                results.append(
                    MemorySearchResult(
                        memory=MemoryResponse.model_validate(memory),
                        relevance_score=round(score, 4),
                    )
                )

        await self.db.commit()
        # Sort: pinned first, then by relevance × importance
        results.sort(
            key=lambda r: (r.memory.is_pinned, r.relevance_score * r.memory.importance_score),
            reverse=True,
        )
        return results

    async def _fulltext_search(
        self, user_id: uuid.UUID, payload: MemorySearchRequest
    ) -> List[MemorySearchResult]:
        """PostgreSQL ilike fallback when ChromaDB is unavailable."""
        query = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.is_archived == False,
                or_(
                    Memory.title.ilike(f"%{payload.query}%"),
                    Memory.content.ilike(f"%{payload.query}%"),
                ),
            )
            .order_by(Memory.is_pinned.desc(), Memory.importance_score.desc())
            .limit(payload.limit)
        )
        if payload.collection_id:
            query = query.where(Memory.collection_id == payload.collection_id)
        if payload.memory_type:
            query = query.where(Memory.memory_type == payload.memory_type)

        result = await self.db.execute(query)
        memories = result.scalars().all()
        return [
            MemorySearchResult(
                memory=MemoryResponse.model_validate(m),
                relevance_score=0.5,
            )
            for m in memories
        ]

    # ─── ChromaDB I/O (sync, runs in thread pool) ─────────────────

    async def _embed_memory(self, memory: Memory) -> Optional[str]:
        try:
            import asyncio
            doc_text = f"{memory.title}\n\n{memory.content}"
            metadata = {
                "user_id": str(memory.user_id),
                "memory_type": memory.memory_type.value,
                "title": memory.title,
                "collection_id": str(memory.collection_id) if memory.collection_id else "",
                "importance": memory.importance_score,
                "is_pinned": str(memory.is_pinned),
            }
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._chroma_add_sync, str(memory.id), doc_text, metadata
            )
        except Exception as exc:
            logger.warning("memory.embed_failed", memory_id=str(memory.id), error=str(exc))
            return None

    def _chroma_add_sync(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> str:
        client = _chroma_client()
        collection = client.get_or_create_collection(
            settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
        return doc_id

    def _chroma_query_sync(
        self,
        query: str,
        user_id: str,
        limit: int,
        collection_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        client = _chroma_client()
        col = client.get_or_create_collection(settings.CHROMA_COLLECTION_NAME)
        where: Dict[str, Any] = {"user_id": user_id}
        if collection_id:
            where["collection_id"] = collection_id

        results = col.query(
            query_texts=[query],
            n_results=min(limit, 20),
            where=where if where else None,
        )
        items: List[Dict[str, Any]] = []
        if results and results.get("ids"):
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 1.0
                items.append({"id": doc_id, "score": max(0.0, 1.0 - distance)})
        return items

    async def delete_embedding(self, embedding_id: str) -> None:
        """Remove a document from ChromaDB."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._chroma_delete_sync, embedding_id)
        except Exception as exc:
            logger.warning("memory.delete_embedding_failed", id=embedding_id, error=str(exc))

    def _chroma_delete_sync(self, doc_id: str) -> None:
        client = _chroma_client()
        col = client.get_or_create_collection(settings.CHROMA_COLLECTION_NAME)
        col.delete(ids=[doc_id])
