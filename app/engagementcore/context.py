"""Persistent context snapshot — thin stub for Stage 14.

Full snapshot build (open tasks, pending evidence, pending approvals,
recent client inputs, active pack) is implemented in Stage 17.
"""
from sqlalchemy.orm import Session

from app.engagementcore.state import get_state, update_state
from app.models.engagement import EngagementState


def build_context_snapshot(db: Session, project_id: str) -> dict:
    """Build a minimal context snapshot from current project state."""
    from app.models.clients import Project
    from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
    from app.models.tasks import Task
    from app.models.workflow import ApprovalRequest, ApprovalStatus

    project = db.get(Project, project_id)
    if project is None:
        return {}

    open_tasks = (
        db.query(Task).filter_by(project_id=project_id)
        .filter(Task.status != "done")
        .count()
    )
    pending_evidence = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open)
        .count()
    )
    pending_approvals = (
        db.query(ApprovalRequest)
        .filter_by(project_id=project_id, status=ApprovalStatus.pending)
        .count()
    )

    return {
        "active_pack": project.pack_id,
        "phase": project.status,
        "open_tasks": open_tasks,
        "pending_evidence_requests": pending_evidence,
        "pending_approvals": pending_approvals,
        "gates": project.gates or {},
    }


def refresh_snapshot(db: Session, project_id: str) -> EngagementState:
    """Rebuild and persist the context snapshot on the EngagementState."""
    snapshot = build_context_snapshot(db, project_id)
    return update_state(db, project_id, context_snapshot=snapshot)
