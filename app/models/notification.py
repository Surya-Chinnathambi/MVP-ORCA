"""Notification model (Stage 22) — unified web/email/telegram inbox."""
import enum
from typing import Any, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class NotificationChannel(str, enum.Enum):
    web = "web"
    email = "email"
    telegram = "telegram"


class NotificationEventType(str, enum.Enum):
    approval_needed = "approval_needed"
    evidence_request_reminder = "evidence_request_reminder"
    deadline = "deadline"
    finding_status_change = "finding_status_change"
    escalation = "escalation"
    scheduled_status_summary = "scheduled_status_summary"


# Keys stripped from payload when recipient has client_contributor role
INTERNAL_ONLY_PAYLOAD_KEYS = frozenset({
    "findings_detail", "severity", "approvals", "internal_notes",
    "audit_trail", "gate_status", "approval_id", "approver_role",
})


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(
        Enum(NotificationChannel, name="notification_channel_enum"),
        default=NotificationChannel.web,
        nullable=False,
    )
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
