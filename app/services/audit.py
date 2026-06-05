"""Central audit trail + approval gateway.

Every mutating path in the application uses these three functions.
This module is the single enforcement point — never bypass it.

record_event   → writes one AuditTrailEvent (append-only)
request_approval → creates ApprovalRequest(status=pending), returns it
decide_approval  → resolves a pending approval, records an audit event
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent


def record_event(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str,
    actor_id: Optional[str] = None,
    project_id: Optional[str] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    reason: Optional[str] = None,
) -> AuditTrailEvent:
    event = AuditTrailEvent(
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        reason=reason,
    )
    db.add(event)
    return event


def request_approval(
    db: Session,
    *,
    project_id: Optional[str] = None,
    target_type: str,
    target_id: str,
    reason: str,
    approver_role: str,
    change_before: Optional[Any] = None,
    change_after: Optional[Any] = None,
    requested_by: Optional[str] = None,
) -> ApprovalRequest:
    # Pre-generate the ID so we can reference it in the audit event
    # without requiring a flush first.
    approval_id = str(uuid.uuid4())
    approval = ApprovalRequest(
        id=approval_id,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        change_before=change_before,
        change_after=change_after,
        reason=reason,
        approver_role=approver_role,
        requested_by=requested_by,
        status=ApprovalStatus.pending,
    )
    db.add(approval)
    record_event(
        db,
        action=f"approval.requested.{target_type}",
        target_type="approval_request",
        target_id=approval_id,
        actor_id=requested_by,
        project_id=project_id,
        after={"approver_role": approver_role, "reason": reason},
    )
    return approval


def decide_approval(
    db: Session,
    *,
    approval_id: str,
    approved: bool,
    decider_id: str,
    reason: Optional[str] = None,
) -> ApprovalRequest:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise ValueError(f"ApprovalRequest {approval_id!r} not found")
    if approval.status != ApprovalStatus.pending:
        raise ValueError(f"Cannot decide approval with status {approval.status!r}")

    new_status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
    approval.status = new_status
    approval.decided_by = decider_id
    approval.decided_at = datetime.now(timezone.utc)

    record_event(
        db,
        action=f"approval.{new_status.value}",
        target_type="approval_request",
        target_id=approval_id,
        actor_id=decider_id,
        project_id=approval.project_id,
        before={"status": "pending"},
        after={"status": new_status.value},
        reason=reason,
    )
    return approval
