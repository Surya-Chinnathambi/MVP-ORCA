"""WorkMode — scoped context views per user activity role.
UserLastContext — persists last active client/project/work_mode per user.
"""
import enum
from typing import Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if __name__ == "__main__":
    pass  # avoid circular import if run directly


class WorkModeName(str, enum.Enum):
    pm = "pm"
    analyst = "analyst"
    reviewer = "reviewer"
    deliverable_builder = "deliverable_builder"
    client_contributor = "client_contributor"


WORK_MODE_SEEDS: list[dict] = [
    {
        "key": "pm",
        "title": "Project Manager",
        "allowed_views": [
            "phase", "open_tasks", "pending_approvals",
            "pending_evidence_requests", "progress", "gates", "active_pack",
        ],
        "default_filters": {"task_status": "open"},
    },
    {
        "key": "analyst",
        "title": "Analyst",
        "allowed_views": [
            "phase", "open_tasks", "pending_evidence_requests",
            "progress", "active_pack", "findings", "evidence_items", "scope_items",
        ],
        "default_filters": {"finding_status": "open"},
    },
    {
        "key": "reviewer",
        "title": "Reviewer",
        "allowed_views": [
            "phase", "findings", "evidence_items", "deliverables", "progress", "gates",
        ],
        "default_filters": {"evidence_reviewer_status": "pending"},
    },
    {
        "key": "deliverable_builder",
        "title": "Deliverable Builder",
        "allowed_views": [
            "phase", "deliverables", "progress", "gates", "findings",
            "evidence_items", "active_pack",
        ],
        "default_filters": {"evidence_lifecycle_state": "classified"},
    },
    {
        "key": "client_contributor",
        "title": "Client Contributor",
        "allowed_views": [
            "phase", "open_tasks", "pending_evidence_requests",
        ],
        "default_filters": {"task_assigned_to_user": True},
    },
]

# Fields stripped from context when resolved as client_contributor
CLIENT_CONTRIBUTOR_STRIP_KEYS = frozenset({
    "pending_approvals", "recent_client_inputs", "gates",
    "internal_notes", "audit_trail",
})


class WorkMode(TimestampMixin, Base):
    __tablename__ = "work_modes"

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    allowed_views: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    default_filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class UserLastContext(TimestampMixin, Base):
    """Stores the last active project / client / work_mode for a user."""
    __tablename__ = "user_last_contexts"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=True
    )
    client_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("clients.id"), nullable=True
    )
    work_mode_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
