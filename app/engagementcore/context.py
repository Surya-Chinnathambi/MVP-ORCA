"""Persistent context snapshot — full implementation for Stage 17.

build_context_snapshot() assembles:
  active_pack       — key/version/lifecycle of the DB-pinned pack
  phase             — current project status
  open_tasks        — up to 10 open tasks (id, title, kind, status)
  pending_evidence_requests — open EvidenceRequests
  pending_approvals — pending ApprovalRequests scoped to this project
  recent_client_inputs — last 5 AuditTrailEvents for the project
  progress          — workstream % (tasks, evidence, findings, objectives) + gates_passed

refresh_snapshot() persists the result to EngagementState.context_snapshot
and EngagementState.progress.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.engagementcore.state import get_state, update_state
from app.models.engagement import EngagementObjective, EngagementState


# ── Progress ──────────────────────────────────────────────────────────────────

def _compute_progress(db: Session, project_id: str) -> dict:
    from app.models.clients import Project
    from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
    from app.models.tasks import Finding, FindingStatus, Task

    def _pct(done: int, total: int) -> int:
        return round(100 * done / total) if total else 0

    tasks_total = db.query(Task).filter_by(project_id=project_id).count()
    tasks_done = db.query(Task).filter_by(project_id=project_id, status="done").count()

    ev_total = db.query(EvidenceRequest).filter_by(project_id=project_id).count()
    ev_done = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.received)
        .count()
    )

    find_total = db.query(Finding).filter_by(project_id=project_id).count()
    # "closed" = remediated or accepted (no explicit closed status in the model)
    find_closed = (
        db.query(Finding)
        .filter(
            Finding.project_id == project_id,
            Finding.status.in_([FindingStatus.remediated.value, FindingStatus.accepted.value]),
        )
        .count()
    )

    obj_total = db.query(EngagementObjective).filter_by(project_id=project_id).count()
    obj_done = db.query(EngagementObjective).filter_by(project_id=project_id, status="complete").count()

    project = db.get(Project, project_id)
    gates = (project.gates or {}) if project else {}
    gates_passed = sum(1 for v in gates.values() if v)

    return {
        "tasks":      {"done": tasks_done, "total": tasks_total, "pct": _pct(tasks_done, tasks_total)},
        "evidence":   {"received": ev_done, "total": ev_total, "pct": _pct(ev_done, ev_total)},
        "findings":   {"closed": find_closed, "total": find_total, "pct": _pct(find_closed, find_total)},
        "objectives": {"complete": obj_done, "total": obj_total, "pct": _pct(obj_done, obj_total)},
        "gates_passed": gates_passed,
    }


# ── Snapshot ──────────────────────────────────────────────────────────────────

def build_context_snapshot(db: Session, project_id: str) -> dict:
    """Build a full context snapshot; does NOT persist it."""
    from app.models.clients import Project
    from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
    from app.models.tasks import Task
    from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent

    project = db.get(Project, project_id)
    if project is None:
        return {}

    # Active pack
    active_pack: dict = {}
    if project.pack_id:
        from app.models.methodology import MethodologyPack
        pack_row = db.get(MethodologyPack, project.pack_id)
        if pack_row:
            active_pack = {
                "id": pack_row.id, "key": pack_row.key,
                "version": pack_row.version, "lifecycle": pack_row.lifecycle,
            }
        else:
            active_pack = {"id": project.pack_id}

    # Open tasks (up to 10)
    open_tasks_rows = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.status != "done")
        .limit(10).all()
    )
    open_tasks = [
        {"id": t.id, "title": t.title, "kind": t.kind, "status": t.status}
        for t in open_tasks_rows
    ]

    # Pending evidence requests
    pending_ev_rows = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open)
        .all()
    )
    pending_evidence_requests = [{"id": e.id, "title": e.title} for e in pending_ev_rows]

    # Pending approvals scoped to project
    pending_appr_rows = (
        db.query(ApprovalRequest)
        .filter_by(project_id=project_id, status=ApprovalStatus.pending)
        .all()
    )
    pending_approvals = [
        {"id": a.id, "target_type": a.target_type, "reason": a.reason}
        for a in pending_appr_rows
    ]

    # Recent client inputs — last 5 audit events for this project
    recent_events = (
        db.query(AuditTrailEvent)
        .filter_by(project_id=project_id)
        .order_by(AuditTrailEvent.ts.desc())
        .limit(5).all()
    )
    recent_client_inputs = [
        {"action": e.action, "target_type": e.target_type, "ts": e.ts.isoformat()}
        for e in recent_events
    ]

    progress = _compute_progress(db, project_id)

    return {
        "active_pack": active_pack,
        "phase": project.status,
        "open_tasks": open_tasks,
        "pending_evidence_requests": pending_evidence_requests,
        "pending_approvals": pending_approvals,
        "recent_client_inputs": recent_client_inputs,
        "progress": progress,
        "gates": project.gates or {},
    }


def refresh_snapshot(db: Session, project_id: str) -> EngagementState:
    """Rebuild and persist the snapshot to EngagementState."""
    snapshot = build_context_snapshot(db, project_id)
    return update_state(
        db, project_id,
        context_snapshot=snapshot,
        progress=snapshot.get("progress", {}),
    )
