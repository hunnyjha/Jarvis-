"""
JARVIS User Model — User accounts and authentication.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.memory import Memory, MemoryCollection
    from app.models.report import Report
    from app.models.research import ResearchSession
    from app.models.security import SecurityInvestigation


class User(BaseModel):
    """User account model."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_lower", "email"),
        Index("ix_users_username_lower", "username"),
        {"comment": "User accounts and authentication"},
    )

    # Core fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (unique)",
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Display username (unique)",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password",
    )

    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        comment="Full display name",
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="URL to user avatar image",
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User biography",
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether the account is active",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user has superuser privileges",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the email has been verified",
    )

    # Session tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful login",
    )

    # Preferences (flexible JSONB)
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="User preferences and settings (JSONB)",
    )

    # Relationships
    research_sessions: Mapped[List["ResearchSession"]] = relationship(
        "ResearchSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    security_investigations: Mapped[List["SecurityInvestigation"]] = relationship(
        "SecurityInvestigation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    memories: Mapped[List["Memory"]] = relationship(
        "Memory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    memory_collections: Mapped[List["MemoryCollection"]] = relationship(
        "MemoryCollection",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
