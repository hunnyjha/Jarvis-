"""
JARVIS Research Models — ResearchSession and ResearchResult.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class ResearchStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchType(str, enum.Enum):
    WEB_SEARCH = "web_search"
    REDDIT_ANALYSIS = "reddit_analysis"
    MULTI_SOURCE = "multi_source"
    DEEP_DIVE = "deep_dive"
    COMPETITIVE = "competitive"


class ResearchSession(BaseModel):
    """A research session initiated by a user."""

    __tablename__ = "research_sessions"
    __table_args__ = (
        Index("ix_research_sessions_user_id", "user_id"),
        Index("ix_research_sessions_status", "status"),
        {"comment": "User-initiated research sessions"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Research session title",
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original research query",
    )
    research_type: Mapped[ResearchType] = mapped_column(
        Enum(ResearchType, name="research_type_enum"),
        nullable=False,
        default=ResearchType.WEB_SEARCH,
    )
    status: Mapped[ResearchStatus] = mapped_column(
        Enum(ResearchStatus, name="research_status_enum"),
        nullable=False,
        default=ResearchStatus.PENDING,
        index=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated summary of findings",
    )
    sources_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional metadata (search params, agent state, etc.)",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if session failed",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="research_sessions")
    results: Mapped[List["ResearchResult"]] = relationship(
        "ResearchResult",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ResearchResult.relevance_score.desc()",
    )

    def __repr__(self) -> str:
        return f"<ResearchSession id={self.id} status={self.status}>"


class ResearchResult(BaseModel):
    """Individual result from a research session."""

    __tablename__ = "research_results"
    __table_args__ = (
        Index("ix_research_results_session_id", "session_id"),
        {"comment": "Individual research results within a session"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Source name (e.g., 'reddit', 'web', 'news')",
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full text content of the result",
    )
    snippet: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Short excerpt of the result",
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="AI-assigned relevance score (0-1)",
    )
    analysis: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI analysis of this result",
    )
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ChromaDB embedding document ID",
    )

    # Relationship
    session: Mapped["ResearchSession"] = relationship(
        "ResearchSession", back_populates="results"
    )

    def __repr__(self) -> str:
        return f"<ResearchResult id={self.id} source={self.source}>"
