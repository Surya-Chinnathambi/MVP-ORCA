import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.tasks import Finding
    from app.models.users import User


class DeliverableKind(str, enum.Enum):
    gap_matrix = "gap_matrix"
    roadmap = "roadmap"
    report = "report"
    summary = "summary"
    tracker = "tracker"
    # Stage 27 — new deliverable kinds
    retest_report = "retest_report"
    advisory_clinic_deck = "advisory_clinic_deck"
    management_summary = "management_summary"
    client_action_plan = "client_action_plan"


class AdvisoryClinic(TimestampMixin, Base):
    __tablename__ = "advisory_clinics"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    agenda: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    linked_finding_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped["Project"] = relationship(back_populates="advisory_clinics")


class Deliverable(TimestampMixin, Base):
    __tablename__ = "deliverables"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Enum(DeliverableKind, name="deliverable_kind_enum"), nullable=False
    )
    format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_released: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="deliverables")


class RemediationAction(TimestampMixin, Base):
    __tablename__ = "remediation_actions"

    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    residual_risk: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship(back_populates="remediation_actions")
    project: Mapped["Project"] = relationship(back_populates="remediation_actions")
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
