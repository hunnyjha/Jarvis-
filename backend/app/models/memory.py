"""
JARVIS Memory Models — long-term semantic memory and collections.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class MemoryType(str, enum.Enum):
    CONVERSATION = "conversation"
    RESEARCH = "research"
    SUBREDDIT_REPORT = "subreddit_report"
    COMPETITOR_REPORT = "competitor_report"
    GROWTH_EXPERIMENT = "growth_experiment"
    DECISION = "decision"
    PREFERENCE = "preference"
    INSIGHT = "insight"
    FACT = "fact"
    NOTE = "note"


class MemoryCollection(BaseModel):
    """Named collection grouping related memories."""

    __tablename__ = "memory_collections"
    # Column-level index=True already creates these indexes; no explicit
    # Index() here to avoid duplicate CREATE INDEX during create_all.
    __table_args__ = {"comment": "Named collections for organizing memories"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    chroma_collection_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="memory_collections")
    memories: Mapped[List["Memory"]] = relationship(
        "Memory", back_populates="collection", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MemoryCollection id={self.id} name={self.name}>"


class Memory(BaseModel):
    """A single memory entry with vector embedding in ChromaDB."""

    __tablename__ = "memories"
    __table_args__ = {"comment": "Long-term semantic memory entries"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type_enum"),
        nullable=False,
        default=MemoryType.NOTE,
        index=True,
    )
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    importance_score: Mapped[float] = mapped_column(default=0.5, nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="memories")
    collection: Mapped[Optional["MemoryCollection"]] = relationship(
        "MemoryCollection", back_populates="memories"
    )

    def __repr__(self) -> str:
        return f"<Memory id={self.id} type={self.memory_type} title={self.title[:40]}>"
