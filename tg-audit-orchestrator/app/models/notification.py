"""Notification model (Stage 22) — unified web/email/telegram inbox."""
import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, _utcnow


class NotificationChannel(str, enum.Enum):
    web = "web"
    email = "email"
    telegram = "telegram"


class NotificationKind(str, enum.Enum):
    approval_needed = "approval_needed"
    evidence_reminder = "evidence_reminder"
    deadline = "deadline"
    finding_status = "finding_status"
    escalation = "escalation"
    status_summary = "status_summary"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    read = "read"
    failed = "failed"


# Keys stripped from payload when recipient has client_contributor role
INTERNAL_ONLY_PAYLOAD_KEYS = frozenset({
    "findings_detail", "severity", "approvals", "internal_notes",
    "audit_trail", "gate_status", "approval_id", "approver_role",
})


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    recipient_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(
        Enum(NotificationChannel, name="notification_channel_enum"),
        default=NotificationChannel.web,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        Enum(NotificationKind, name="notification_kind_enum"),
        nullable=False,
    )
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(NotificationStatus, name="notification_status_enum"),
        default=NotificationStatus.pending,
        nullable=False,
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_user_id])
