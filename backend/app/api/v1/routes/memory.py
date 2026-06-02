"""Memory routes — store, search, retrieve, manage collections."""
from __future__ import annotations

import uuid
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.memory import Memory, MemoryCollection
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.memory import (
    MemoryCollectionCreate,
    MemoryCollectionResponse,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryStoreRequest,
)
from app.services.memory_service import MemoryService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/store", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def store_memory(
    payload: MemoryStoreRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Memory:
    """Store a new memory with vector embedding."""
    service = MemoryService(db)
    memory = await service.store(current_user.id, payload)
    logger.info("memory.stored", memory_id=str(memory.id), user_id=str(current_user.id))
    return memory


@router.post("/search", response_model=List[MemorySearchResult])
async def search_memories(
    payload: MemorySearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MemorySearchResult]:
    """Semantic search across user memories using vector similarity."""
    service = MemoryService(db)
    return await service.search(current_user.id, payload)


@router.get("/", response_model=PaginatedResponse[MemoryResponse])
async def list_memories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    collection_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MemoryResponse]:
    """List memories with optional collection filter."""
    query = select(Memory).where(Memory.user_id == current_user.id, Memory.is_archived == False)
    count_query = select(func.count(Memory.id)).where(
        Memory.user_id == current_user.id, Memory.is_archived == False
    )
    if collection_id:
        query = query.where(Memory.collection_id == collection_id)
        count_query = count_query.where(Memory.collection_id == collection_id)

    total = await db.scalar(count_query)
    result = await db.execute(
        query.order_by(Memory.is_pinned.desc(), Memory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse.create(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == current_user.id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    await db.delete(memory)
    await db.commit()


@router.post("/collections", response_model=MemoryCollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: MemoryCollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryCollection:
    collection = MemoryCollection(user_id=current_user.id, **payload.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.get("/collections", response_model=List[MemoryCollectionResponse])
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MemoryCollection]:
    result = await db.execute(
        select(MemoryCollection)
        .where(MemoryCollection.user_id == current_user.id)
        .order_by(MemoryCollection.is_default.desc(), MemoryCollection.name)
    )
    return list(result.scalars().all())
