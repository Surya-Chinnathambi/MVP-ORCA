"""Central audit trail + approval gateway.

Every mutating path in the application uses these three functions.
This module is the single enforcement point — never bypass it.

record_event   → writes one AuditTrailEvent (append-only)
request_approval → creates ApprovalRequest(status=requested), returns it
decide_approval  → resolves a requested approval, records an audit event
cancel_approval  → moves an approval to cancelled (e.g. withdrawn request)
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.workflow import (
    APPROVAL_FINAL_STATES,
    ApprovalRequest,
    ApprovalStatus,
    AuditTrailEvent,
)


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
        status=ApprovalStatus.requested.value,
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

    current = ApprovalStatus(approval.status)
    if current in APPROVAL_FINAL_STATES:
        raise ValueError(
            f"Cannot decide approval {approval_id!r}: already finalized ({current.value})"
        )
    if current not in (ApprovalStatus.requested, ApprovalStatus.pending):
        raise ValueError(
            f"Cannot decide approval {approval_id!r}: status is {current.value!r}, expected 'requested'"
        )

    # RBAC check: decider must hold the required approver_role
    from app.models.users import Permission, Role
    required_role = db.query(Role).filter_by(name=approval.approver_role).first()
    if required_role is not None:
        has_role = db.query(Permission).filter_by(
            user_id=decider_id, role_id=required_role.id
        ).first()
        if has_role is None:
            raise ValueError(
                f"Decider does not hold required approver role: {approval.approver_role!r}"
            )

    new_status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
    approval.status = new_status.value
    approval.decided_by = decider_id
    approval.decided_at = datetime.now(timezone.utc)

    record_event(
        db,
        action=f"approval.{new_status.value}",
        target_type="approval_request",
        target_id=approval_id,
        actor_id=decider_id,
        project_id=approval.project_id,
        before={"status": current.value},
        after={"status": new_status.value},
        reason=reason,
    )
    return approval


def cancel_approval(
    db: Session,
    *,
    approval_id: str,
    actor_id: str,
    reason: Optional[str] = None,
) -> ApprovalRequest:
    """Cancel a requested approval that was withdrawn or has no applicable handler."""
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise ValueError(f"ApprovalRequest {approval_id!r} not found")

    current = ApprovalStatus(approval.status)
    if current in APPROVAL_FINAL_STATES:
        raise ValueError(
            f"Cannot cancel approval {approval_id!r}: already finalized ({current.value})"
        )

    approval.status = ApprovalStatus.cancelled.value
    record_event(
        db,
        action="approval.cancelled",
        target_type="approval_request",
        target_id=approval_id,
        actor_id=actor_id,
        project_id=approval.project_id,
        before={"status": current.value},
        after={"status": "cancelled"},
        reason=reason,
    )
    return approval
