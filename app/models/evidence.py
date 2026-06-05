import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, _utcnow

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.scope import Requirement
    from app.models.users import User


class EvidenceRequestStatus(str, enum.Enum):
    open = "open"
    received = "received"
    waived = "waived"


class ReviewerStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class EvidenceRequest(TimestampMixin, Base):
    __tablename__ = "evidence_requests"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    requirement_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("requirements.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(EvidenceRequestStatus, name="evidence_request_status_enum"),
        default=EvidenceRequestStatus.open,
        nullable=False,
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="evidence_requests")
    requirement: Mapped[Optional["Requirement"]] = relationship(
        back_populates="evidence_requests"
    )
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="evidence_request"
    )


class EvidenceItem(TimestampMixin, Base):
    __tablename__ = "evidence_items"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    evidence_request_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("evidence_requests.id"), nullable=True
    )
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sensitivity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewer_status: Mapped[str] = mapped_column(
        Enum(ReviewerStatus, name="reviewer_status_enum"),
        default=ReviewerStatus.pending,
        nullable=False,
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="evidence_items")
    evidence_request: Mapped[Optional["EvidenceRequest"]] = relationship(
        back_populates="evidence_items"
    )
