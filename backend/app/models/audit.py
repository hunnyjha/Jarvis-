"""
JARVIS Audit Log Model — records all user actions for compliance and debugging.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(BaseModel):
    """Immutable audit log entry for every user action."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_created_at", "created_at"),
        {"comment": "Immutable audit log for all user actions"},
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action (null for system actions)",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action performed (e.g., 'user.login', 'reddit.analyze')",
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Type of resource affected (e.g., 'subreddit_analysis')",
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ID of the affected resource",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Additional action-specific data"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} user_id={self.user_id}>"
