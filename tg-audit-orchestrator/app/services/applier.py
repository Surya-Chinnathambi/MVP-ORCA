"""Apply the outcome of a decided approval to its target entity.

Dispatcher called after decide_approval() when approved=True.
After successful mutation, sets approval.status = 'applied' and stamps applied_at/applied_by.
If no handler is registered for the target_type, sets status to 'cancelled'.

Registered handlers (approval.target_type → function):
  scope_item              → ScopeItem.approved = True
  evidence_request_waiver → EvidenceRequest.status = "waived"
  task_cancellation       → Task.status = "cancelled"
  evidence_rejection      → EvidenceItem.reviewer_status = "rejected"
  finding_severity_change → Finding.severity = change_after["severity"]
  finding_status_change   → Finding.status = change_after["status"]
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus, ReviewerStatus
from app.models.scope import ScopeItem
from app.models.tasks import Finding, Task
from app.models.workflow import APPROVAL_FINAL_STATES, ApprovalRequest, ApprovalStatus
from app.services.audit import record_event


def apply_approval(
    db: Session,
    approval: ApprovalRequest,
    *,
    actor_id: Optional[str] = None,
) -> None:
    """Mutate the target entity to reflect an approved decision.

    Sets approval.status → 'applied' on success, or → 'cancelled' if no handler exists.
    Raises ValueError if the approval is not in 'approved' state.
    Raises ValueError if the approval is already finalized.
    """
    current = ApprovalStatus(approval.status)
    if current in APPROVAL_FINAL_STATES:
        raise ValueError(
            f"ApprovalRequest {approval.id!r} is already finalized ({current.value}); cannot apply."
        )
    if current != ApprovalStatus.approved:
        raise ValueError(
            f"ApprovalRequest {approval.id!r} is not approved (status={current.value!r}); cannot apply."
        )

    handlers = {
        "scope_item":              _apply_scope_item,
        "evidence_request_waiver": _apply_er_waiver,
        "task_cancellation":       _apply_task_cancel,
        "evidence_rejection":      _apply_evidence_rejection,
        "finding_severity_change": _apply_finding_severity,
        "finding_status_change":   _apply_finding_status,
        "methodology_pack":        _apply_pack_lifecycle,
    }
    handler = handlers.get(approval.target_type)
    stamped_actor = actor_id or approval.decided_by

    if handler:
        handler(db, approval)
        approval.status = ApprovalStatus.applied.value
        approval.applied_at = datetime.now(timezone.utc)
        approval.applied_by = stamped_actor
        record_event(
            db,
            action="approval.applied",
            target_type="approval_request",
            target_id=approval.id,
            actor_id=stamped_actor,
            project_id=approval.project_id,
            before={"status": "approved"},
            after={"status": "applied"},
        )
    else:
        # No handler registered — mark as cancelled (withdrawn / not applicable)
        approval.status = ApprovalStatus.cancelled.value
        record_event(
            db,
            action="approval.cancelled",
            target_type="approval_request",
            target_id=approval.id,
            actor_id=stamped_actor,
            project_id=approval.project_id,
            before={"status": "approved"},
            after={"status": "cancelled"},
            reason=f"No handler for target_type={approval.target_type!r}",
        )


def _apply_scope_item(db: Session, approval: ApprovalRequest) -> None:
    item = db.get(ScopeItem, approval.target_id)
    if item:
        item.approved = True


def _apply_er_waiver(db: Session, approval: ApprovalRequest) -> None:
    er = db.get(EvidenceRequest, approval.target_id)
    if er:
        er.status = EvidenceRequestStatus.waived


def _apply_task_cancel(db: Session, approval: ApprovalRequest) -> None:
    task = db.get(Task, approval.target_id)
    if task:
        task.status = "cancelled"


def _apply_evidence_rejection(db: Session, approval: ApprovalRequest) -> None:
    item = db.get(EvidenceItem, approval.target_id)
    if item:
        item.reviewer_status = ReviewerStatus.rejected


def _apply_finding_severity(db: Session, approval: ApprovalRequest) -> None:
    finding = db.get(Finding, approval.target_id)
    if finding and approval.change_after:
        finding.severity = approval.change_after["severity"]


def _apply_finding_status(db: Session, approval: ApprovalRequest) -> None:
    finding = db.get(Finding, approval.target_id)
    if finding and approval.change_after:
        finding.status = approval.change_after["status"]


def _apply_pack_lifecycle(db: Session, approval: ApprovalRequest) -> None:
    from app.models.methodology import MethodologyPack, PackLifecycle
    mp = db.get(MethodologyPack, approval.target_id)
    if mp and approval.change_after:
        mp.lifecycle = approval.change_after["lifecycle"]
