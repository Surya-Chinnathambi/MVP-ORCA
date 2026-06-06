"""Workflow state machine for Project, Finding, and Task.

Each transition is validated against an allowed-transitions table.
Transitions that are approval triggers are routed through the audit gateway.

Project states:  draft → scoped → active → review → client_review → final → closed → archived
Finding states:  draft → in_review → approved → client_shared → remediation_planned
                 → retest_pending → closed / risk_accepted
Task states:     planned → assigned → in_progress → blocked → review → complete / cancelled

Approval-gated transitions (routed through request_approval):
  - Finding: in_review → approved  (requires approver_role=reviewer)
  - Finding: approved  → client_shared (requires approver_role=partner)
  - Project: review    → client_review (requires approver_role=partner)
  - Project: final     → closed      (requires approver_role=partner)
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.tasks import Finding, FindingStatus, Task, TaskStatus
from app.services.audit import record_event, request_approval

# ── Transition tables ─────────────────────────────────────────────────────────

_FINDING_TRANSITIONS: dict[str, list[str]] = {
    FindingStatus.draft.value:               [FindingStatus.in_review.value],
    FindingStatus.in_review.value:           [FindingStatus.approved.value, FindingStatus.draft.value],
    FindingStatus.approved.value:            [FindingStatus.client_shared.value, FindingStatus.remediation_planned.value],
    FindingStatus.client_shared.value:       [FindingStatus.remediation_planned.value],
    FindingStatus.remediation_planned.value: [FindingStatus.retest_pending.value, FindingStatus.closed.value, FindingStatus.risk_accepted.value],
    FindingStatus.retest_pending.value:      [FindingStatus.closed.value, FindingStatus.risk_accepted.value, FindingStatus.in_review.value],
    FindingStatus.closed.value:              [],
    FindingStatus.risk_accepted.value:       [],
    # Legacy states — map to nearest new state for migration; allow transition out
    FindingStatus.open.value:               [FindingStatus.in_review.value, FindingStatus.draft.value],
    FindingStatus.remediated.value:         [FindingStatus.closed.value],
    FindingStatus.accepted.value:           [FindingStatus.risk_accepted.value],
}

_TASK_TRANSITIONS: dict[str, list[str]] = {
    TaskStatus.planned.value:     [TaskStatus.assigned.value, TaskStatus.cancelled.value],
    TaskStatus.assigned.value:    [TaskStatus.in_progress.value, TaskStatus.planned.value, TaskStatus.cancelled.value],
    TaskStatus.in_progress.value: [TaskStatus.blocked.value, TaskStatus.review.value, TaskStatus.cancelled.value],
    TaskStatus.blocked.value:     [TaskStatus.in_progress.value, TaskStatus.cancelled.value],
    TaskStatus.review.value:      [TaskStatus.complete.value, TaskStatus.in_progress.value],
    TaskStatus.complete.value:    [],
    TaskStatus.cancelled.value:   [],
}

_PROJECT_TRANSITIONS: dict[str, list[str]] = {
    "draft":         ["scoped"],
    "scoped":        ["active", "draft"],
    "active":        ["review"],
    "review":        ["client_review", "active"],
    "client_review": ["final", "review"],
    "final":         ["closed"],
    "closed":        ["archived"],
    "archived":      [],
    # Legacy states
    "setup":         ["draft", "active"],
}

# Transitions that require an ApprovalRequest before proceeding
_FINDING_APPROVAL_TRIGGERS: dict[tuple[str, str], str] = {
    (FindingStatus.in_review.value, FindingStatus.approved.value): "reviewer",
    (FindingStatus.approved.value, FindingStatus.client_shared.value): "partner",
}

_PROJECT_APPROVAL_TRIGGERS: dict[tuple[str, str], str] = {
    ("review", "client_review"): "partner",
    ("final", "closed"): "partner",
}


# ── Finding transitions ───────────────────────────────────────────────────────

class TransitionError(ValueError):
    pass


def transition_finding(
    db: Session,
    finding: Finding,
    to_status: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Finding:
    """Transition a finding to a new status.

    For approval-gated transitions, creates an ApprovalRequest and raises
    TransitionError — the caller must resolve the approval before retrying.
    """
    from_status = finding.status
    allowed = _FINDING_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise TransitionError(
            f"Finding transition {from_status!r} → {to_status!r} is not allowed. "
            f"Allowed: {allowed}"
        )

    trigger_key = (from_status, to_status)
    if trigger_key in _FINDING_APPROVAL_TRIGGERS:
        approver_role = _FINDING_APPROVAL_TRIGGERS[trigger_key]
        request_approval(
            db,
            project_id=finding.project_id,
            target_type="finding",
            target_id=finding.id,
            reason=reason or f"Finding status change: {from_status} → {to_status}",
            approver_role=approver_role,
            change_before={"status": from_status},
            change_after={"status": to_status},
        )
        raise TransitionError(
            f"Finding transition {from_status!r} → {to_status!r} requires approval "
            f"by role '{approver_role}'. ApprovalRequest created."
        )

    finding.status = to_status
    record_event(
        db,
        action="finding.status_changed",
        target_type="finding",
        target_id=finding.id,
        project_id=finding.project_id,
        actor_id=actor_id,
        before={"status": from_status},
        after={"status": to_status, "reason": reason},
    )
    return finding


# ── Task transitions ──────────────────────────────────────────────────────────

def transition_task(
    db: Session,
    task: Task,
    to_status: str,
    actor_id: Optional[str] = None,
) -> Task:
    from_status = task.status
    allowed = _TASK_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise TransitionError(
            f"Task transition {from_status!r} → {to_status!r} is not allowed. "
            f"Allowed: {allowed}"
        )
    task.status = to_status
    record_event(
        db,
        action="task.status_changed",
        target_type="task",
        target_id=task.id,
        project_id=task.project_id,
        actor_id=actor_id,
        before={"status": from_status},
        after={"status": to_status},
    )
    return task


# ── Project transitions ───────────────────────────────────────────────────────

def transition_project(
    db: Session,
    project: Project,
    to_status: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Project:
    from_status = project.status
    allowed = _PROJECT_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise TransitionError(
            f"Project transition {from_status!r} → {to_status!r} is not allowed. "
            f"Allowed: {allowed}"
        )

    trigger_key = (from_status, to_status)
    if trigger_key in _PROJECT_APPROVAL_TRIGGERS:
        approver_role = _PROJECT_APPROVAL_TRIGGERS[trigger_key]
        request_approval(
            db,
            project_id=project.id,
            target_type="project",
            target_id=project.id,
            reason=reason or f"Project status change: {from_status} → {to_status}",
            approver_role=approver_role,
            change_before={"status": from_status},
            change_after={"status": to_status},
        )
        raise TransitionError(
            f"Project transition {from_status!r} → {to_status!r} requires approval "
            f"by role '{approver_role}'. ApprovalRequest created."
        )

    project.status = to_status
    record_event(
        db,
        action="project.status_changed",
        target_type="project",
        target_id=project.id,
        project_id=project.id,
        actor_id=actor_id,
        before={"status": from_status},
        after={"status": to_status, "reason": reason},
    )
    return project


# ── Migration backfill helpers ────────────────────────────────────────────────

def migrate_finding_statuses(db: Session) -> int:
    """Backfill legacy finding statuses to nearest new state. Returns count updated."""
    _LEGACY_MAP = {
        FindingStatus.open.value: FindingStatus.in_review.value,
        FindingStatus.remediated.value: FindingStatus.closed.value,
        FindingStatus.accepted.value: FindingStatus.risk_accepted.value,
    }
    count = 0
    for finding in db.query(Finding).all():
        new_status = _LEGACY_MAP.get(finding.status)
        if new_status:
            finding.status = new_status
            count += 1
    db.flush()
    return count


def migrate_task_statuses(db: Session) -> int:
    """Backfill legacy task statuses ('open') to 'planned'. Returns count updated."""
    count = 0
    for task in db.query(Task).all():
        if task.status == "open":
            task.status = TaskStatus.planned.value
            count += 1
    db.flush()
    return count
