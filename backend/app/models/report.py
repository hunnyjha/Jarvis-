"""
JARVIS Report Model — generated reports in multiple formats.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class ReportType(str, enum.Enum):
    SUBREDDIT_ANALYSIS = "subreddit_analysis"
    TOPIC_DISCOVERY = "topic_discovery"
    SECURITY_INVESTIGATION = "security_investigation"
    RESEARCH_SESSION = "research_session"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    GROWTH_STRATEGY = "growth_strategy"
    CUSTOM = "custom"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class ReportStatus(str, enum.Enum):
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Report(BaseModel):
    """Generated report in a specified format."""

    __tablename__ = "reports"
    __table_args__ = {"comment": "Generated analysis reports"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum"),
        nullable=False,
        default=ReportStatus.GENERATING,
        index=True,
    )

    # Content
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Structured report content"
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format_enum"),
        nullable=False,
        default=ReportFormat.MARKDOWN,
    )

    # File storage
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Source reference
    source_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="ID of the source entity (analysis, session, etc.)"
    )

    # Sharing
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} status={self.status}>"
