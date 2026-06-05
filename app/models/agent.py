"""AgentDraft — editable output of an AI agent (Stage 23).

Agents never commit changes directly. Their output lands here as a draft
with status="draft". A human must accept (or reject) via the normal API,
which then flows through the approval gateway if the change hits a trigger.
"""
import enum
from typing import Any, Optional

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class AgentType(str, enum.Enum):
    classify_evidence = "classify_evidence"
    draft_finding = "draft_finding"
    map_requirements = "map_requirements"
    qa_assist = "qa_assist"
    draft_report_section = "draft_report_section"
    summarize_status = "summarize_status"


class DraftStatus(str, enum.Enum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"


class AgentDraft(TimestampMixin, Base):
    """Append-only record of one AI agent suggestion awaiting human review."""
    __tablename__ = "agent_drafts"

    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    agent_type: Mapped[str] = mapped_column(
        Enum(AgentType, name="agent_type_enum"), nullable=False
    )
    payload: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(DraftStatus, name="draft_status_enum"),
        default=DraftStatus.draft,
        nullable=False,
    )
    requested_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    accepted_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped[Optional["Project"]] = relationship("Project")
    requester: Mapped[Optional["User"]] = relationship("User", foreign_keys=[requested_by])
    acceptor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[accepted_by])
