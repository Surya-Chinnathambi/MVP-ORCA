"""EngagementState and EngagementObjective models.

EngagementState — 1:1 with Project; the persistent context store.
EngagementObjective — N:1 with Project; service-neutral execution primitives.
"""
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Project


class EngagementState(TimestampMixin, Base):
    __tablename__ = "engagement_states"
    __table_args__ = (UniqueConstraint("project_id", name="uq_engagement_state_project"),)

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, unique=True
    )
    phase: Mapped[str] = mapped_column(String(50), default="setup", nullable=False)
    progress: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    blockers: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    context_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="engagement_state")


class EngagementObjective(TimestampMixin, Base):
    __tablename__ = "engagement_objectives"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    depends_on: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    linked_requirement_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    linked_evidence_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="objectives")
