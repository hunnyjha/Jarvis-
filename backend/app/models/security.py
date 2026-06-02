"""
JARVIS Security Models — SecurityInvestigation and SecurityFinding.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class InvestigationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationType(str, enum.Enum):
    ACCOUNT_SCAN = "account_scan"
    IDENTITY_SEARCH = "identity_search"
    THREAT_ASSESSMENT = "threat_assessment"
    OSINT_COLLECTION = "osint_collection"
    BACKGROUND_CHECK = "background_check"


class SeverityLevel(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingType(str, enum.Enum):
    PERSONAL_INFO = "personal_info"
    SOCIAL_PRESENCE = "social_presence"
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    RISK_INDICATOR = "risk_indicator"
    TIMELINE_EVENT = "timeline_event"
    ASSOCIATION = "association"
    ANOMALY = "anomaly"


class SecurityInvestigation(BaseModel):
    """OSINT / security investigation initiated by a user."""

    __tablename__ = "security_investigations"
    __table_args__ = (
        {"comment": "Security and OSINT investigations"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    target: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Target of investigation (username, URL, etc.)",
    )
    investigation_type: Mapped[InvestigationType] = mapped_column(
        Enum(InvestigationType, name="investigation_type_enum"),
        nullable=False,
        default=InvestigationType.ACCOUNT_SCAN,
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus, name="investigation_status_enum"),
        nullable=False,
        default=InvestigationStatus.PENDING,
        index=True,
    )

    # Results
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Overall risk score (0-100)",
    )
    risk_level: Mapped[Optional[SeverityLevel]] = mapped_column(
        Enum(SeverityLevel, name="severity_level_enum"),
        nullable=True,
    )

    # AI summary
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Raw data
    raw_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw collected data",
    )
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="security_investigations"
    )
    findings: Mapped[List["SecurityFinding"]] = relationship(
        "SecurityFinding",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="SecurityFinding.severity.desc()",
    )

    def __repr__(self) -> str:
        return f"<SecurityInvestigation id={self.id} target={self.target}>"


class SecurityFinding(BaseModel):
    """Individual finding from a security investigation."""

    __tablename__ = "security_findings"
    __table_args__ = (
        {"comment": "Individual findings within a security investigation"},
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finding_type: Mapped[FindingType] = mapped_column(
        Enum(FindingType, name="finding_type_enum"),
        nullable=False,
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        Enum(SeverityLevel, name="severity_level_enum"),
        nullable=False,
        default=SeverityLevel.INFO,
        index=True,
    )
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Supporting evidence for the finding",
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="AI confidence score (0-1)",
    )
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    investigation: Mapped["SecurityInvestigation"] = relationship(
        "SecurityInvestigation", back_populates="findings"
    )

    def __repr__(self) -> str:
        return f"<SecurityFinding id={self.id} severity={self.severity}>"
