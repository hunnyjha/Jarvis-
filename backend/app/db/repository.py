"""
Generic async repository pattern — typed CRUD operations for all models.
Eliminates repeated select/count boilerplate across route handlers.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class Repository(Generic[ModelT]):
    """Typed async repository providing common CRUD operations."""

    def __init__(self, model: Type[ModelT], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get(self, id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[ModelT]:
        query = select(self.model).where(self.model.id == id)
        if user_id and hasattr(self.model, "user_id"):
            query = query.where(self.model.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_with_relations(
        self, id: uuid.UUID, load: List[Any], user_id: Optional[uuid.UUID] = None
    ) -> Optional[ModelT]:
        query = select(self.model).where(self.model.id == id)
        if user_id and hasattr(self.model, "user_id"):
            query = query.where(self.model.user_id == user_id)
        for rel in load:
            query = query.options(selectinload(rel))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: Any = None,
        filters: Optional[List[Any]] = None,
    ) -> tuple[Sequence[ModelT], int]:
        base_query = select(self.model)
        count_query = select(func.count(self.model.id))

        if user_id and hasattr(self.model, "user_id"):
            base_query = base_query.where(self.model.user_id == user_id)
            count_query = count_query.where(self.model.user_id == user_id)

        if filters:
            for f in filters:
                base_query = base_query.where(f)
                count_query = count_query.where(f)

        if order_by is not None:
            base_query = base_query.order_by(order_by)
        elif hasattr(self.model, "created_at"):
            base_query = base_query.order_by(self.model.created_at.desc())

        total = await self.db.scalar(count_query) or 0
        result = await self.db.execute(
            base_query.offset((page - 1) * page_size).limit(page_size)
        )
        items = result.scalars().all()
        return items, total

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.db.delete(instance)
        await self.db.flush()

    async def count(
        self, user_id: Optional[uuid.UUID] = None, filters: Optional[List[Any]] = None
    ) -> int:
        query = select(func.count(self.model.id))
        if user_id and hasattr(self.model, "user_id"):
            query = query.where(self.model.user_id == user_id)
        if filters:
            for f in filters:
                query = query.where(f)
        return await self.db.scalar(query) or 0

    async def exists(self, id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> bool:
        return await self.get(id, user_id) is not None
