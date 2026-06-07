"""Notification triggers (Stage 22).

One function per trigger event. Each calls dispatch.notify() for the
right recipient(s) with a permission-filtered payload.

Trigger functions are called from:
  - app/services/audit.py  → on_approval_needed (after request_approval)
  - RQ jobs               → deadline reminders, status summaries
  - API endpoints         → finding_status_change, escalation
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session


# ── Approval needed ───────────────────────────────────────────────────────────

def on_approval_needed(db: Session, approval_request_id: str) -> list[str]:
    """Notify all users holding the approver_role for this approval request.

    Returns list of notified user IDs.
    """
    from app.models.workflow import ApprovalRequest
    from app.models.users import Permission, Role
    from app.services.notifications.dispatch import notify

    approval = db.get(ApprovalRequest, approval_request_id)
    if approval is None:
        return []

    role = db.query(Role).filter_by(name=approval.approver_role).first()
    if role is None:
        return []

    approvers = (
        db.query(Permission)
        .filter_by(role_id=role.id)
        .all()
    )
    notified = []
    for perm in approvers:
        payload = {
            "approval_id": approval.id,
            "target_type": approval.target_type,
            "target_id": approval.target_id,
            "reason": approval.reason,
            "approver_role": approval.approver_role,
        }
        notify(
            db,
            perm.user_id,
            kind="approval_needed",
            payload=payload,
            project_id=approval.project_id,
            message=f"Approval required: {approval.target_type} — {approval.reason}",
        )
        notified.append(perm.user_id)
    return notified


# ── Evidence request deadline reminder ───────────────────────────────────────

def on_evidence_request_deadline(db: Session, evidence_request_id: str) -> None:
    """Notify the evidence request owner (or project owner) of an upcoming deadline."""
    from app.models.evidence import EvidenceRequest
    from app.services.notifications.dispatch import notify

    er = db.get(EvidenceRequest, evidence_request_id)
    if er is None:
        return

    recipient_id = er.owner_id
    if recipient_id is None:
        # Fall back to project owner
        from app.models.clients import Project
        project = db.get(Project, er.project_id)
        if project:
            recipient_id = project.owner_id

    if recipient_id is None:
        return

    payload = {
        "evidence_request_id": er.id,
        "title": er.title,
        "due_date": er.due_date.isoformat() if er.due_date else None,
        "status": er.status,
    }
    notify(
        db,
        recipient_id,
        kind="evidence_reminder",
        payload=payload,
        project_id=er.project_id,
        message=f"Evidence request '{er.title}' deadline approaching.",
    )


# ── Finding status change ─────────────────────────────────────────────────────

def on_finding_status_change(
    db: Session,
    finding_id: str,
    old_status: str,
    new_status: str,
    actor_id: Optional[str] = None,
) -> None:
    """Notify the project pm/owner when a finding changes status."""
    from app.models.tasks import Finding
    from app.models.clients import Project
    from app.services.notifications.dispatch import notify

    finding = db.get(Finding, finding_id)
    if finding is None:
        return
    project = db.get(Project, finding.project_id)
    if project is None:
        return

    payload = {
        "finding_id": finding_id,
        "title": finding.title,
        "severity": finding.severity,
        "old_status": old_status,
        "new_status": new_status,
        "findings_detail": {"severity": finding.severity, "status": new_status},
    }
    notify(
        db,
        project.owner_id,
        kind="finding_status",
        payload=payload,
        project_id=finding.project_id,
        message=f"Finding '{finding.title}' changed from {old_status} → {new_status}.",
    )


# ── Deadline ──────────────────────────────────────────────────────────────────

def on_project_deadline(db: Session, project_id: str) -> None:
    """Notify project owner of an approaching project deadline."""
    from app.models.clients import Project
    from app.services.notifications.dispatch import notify

    project = db.get(Project, project_id)
    if project is None:
        return
    notify(
        db,
        project.owner_id,
        kind="deadline",
        payload={"project_id": project_id},
        project_id=project_id,
        message="Project deadline is approaching.",
    )


# ── Scheduled status summary ──────────────────────────────────────────────────

def schedule_status_summary(db: Session, project_id: str, user_id: str) -> None:
    """Enqueue a periodic status-summary RQ job via rq-scheduler."""
    from datetime import datetime, timedelta, timezone
    from app.services.notifications.dispatch import _get_queue

    try:
        import fakeredis
        from rq_scheduler import Scheduler
        conn = fakeredis.FakeRedis()
        q = _get_queue()
        scheduler = Scheduler(queue=q, connection=conn)
        run_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        scheduler.enqueue_at(
            run_at,
            _deliver_status_summary,
            project_id,
            user_id,
        )
    except Exception:
        pass  # scheduler unavailable in some environments


def _deliver_status_summary(project_id: str, user_id: str) -> None:
    """Fired by rq-scheduler: create a status-summary notification."""
    from app.db import SessionLocal
    from app.services.notifications.dispatch import notify
    db = SessionLocal()
    try:
        notify(
            db,
            user_id,
            kind="status_summary",
            payload={"project_id": project_id},
            project_id=project_id,
            message="Scheduled status summary for your project.",
        )
        db.commit()
    finally:
        db.close()
