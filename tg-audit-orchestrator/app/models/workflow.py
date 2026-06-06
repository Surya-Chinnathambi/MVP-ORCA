import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, _utcnow

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.users import User


class ApprovalStatus(str, enum.Enum):
    # Full Spec §12 — 5-state lifecycle
    draft = "draft"
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    applied = "applied"
    cancelled = "cancelled"
    # Legacy alias kept for backfill only — maps to 'requested'
    pending = "pending"


# States where no further edits are allowed (immutable after finalization)
APPROVAL_FINAL_STATES = {
    ApprovalStatus.applied,
    ApprovalStatus.rejected,
    ApprovalStatus.cancelled,
}


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    change_before: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    change_after: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approver_role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(ApprovalStatus, name="approval_status_enum"),
        default=ApprovalStatus.requested.value,
        nullable=False,
    )
    decided_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # C4 additions — stamped by applier after successful mutation
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    project: Mapped[Optional["Project"]] = relationship(back_populates="approval_requests")
    requester: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[requested_by]
    )
    decider: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[decided_by]
    )
    applier: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[applied_by]
    )


class AuditTrailEvent(TimestampMixin, Base):
    """Append-only event log. Never update or delete rows."""

    __tablename__ = "audit_trail_events"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    actor_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    before: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    project: Mapped[Optional["Project"]] = relationship(back_populates="audit_events")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])
