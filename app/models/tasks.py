import enum
from datetime import date
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

# Re-export for convenience
__all__ = [
    "TaskKind", "TaskStatus", "FindingSeverity", "FindingStatus", "FindingSource",
    "Task", "Finding",
]

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.scope import Requirement
    from app.models.users import User
    from app.models.delivery import RemediationAction


class TaskKind(str, enum.Enum):
    interview = "interview"
    workshop = "workshop"
    test = "test"
    evidence_request = "evidence_request"
    review = "review"
    remediation = "remediation"


class FindingSeverity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingStatus(str, enum.Enum):
    # Stage 27 — full spec state machine
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    client_shared = "client_shared"
    remediation_planned = "remediation_planned"
    retest_pending = "retest_pending"
    closed = "closed"
    risk_accepted = "risk_accepted"
    # Legacy (kept for migration backfill)
    open = "open"
    remediated = "remediated"
    accepted = "accepted"


class TaskStatus(str, enum.Enum):
    planned = "planned"
    assigned = "assigned"
    in_progress = "in_progress"
    blocked = "blocked"
    review = "review"
    complete = "complete"
    cancelled = "cancelled"


class FindingSource(str, enum.Enum):
    manual = "manual"
    ptorc = "ptorc"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project_id", "project_id"),)

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Enum(TaskKind, name="task_kind_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    assignee_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    assignee: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assignee_id]
    )


class Finding(TimestampMixin, Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_project_id", "project_id"),
        Index("ix_findings_severity", "severity"),
    )

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    requirement_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("requirements.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        Enum(FindingSeverity, name="finding_severity_enum"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(FindingStatus, name="finding_status_enum"),
        default=FindingStatus.open,
        nullable=False,
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    evidence_item_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(
        Enum(FindingSource, name="finding_source_enum"),
        default=FindingSource.manual,
        nullable=False,
    )
    # Stage 26 — PT-Orc v2 import fields
    retest_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phase_tag: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ptorc_run_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pack_scoped_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="findings")
    requirement: Mapped[Optional["Requirement"]] = relationship(
        "Requirement", back_populates="findings", foreign_keys=[requirement_id]
    )
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    remediation_actions: Mapped[list["RemediationAction"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
