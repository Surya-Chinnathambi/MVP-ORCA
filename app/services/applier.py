"""Apply the outcome of a decided approval to its target entity.

Dispatcher called by POST /approvals/{id}/decide after decide_approval().
Stage 8 expands this to all controlled target types.

Registered handlers (approval.target_type → function):
  scope_item              → ScopeItem.approved = True
  evidence_request_waiver → EvidenceRequest.status = "waived"
  task_cancellation       → Task.status = "cancelled"
"""
from sqlalchemy.orm import Session

from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.scope import ScopeItem
from app.models.tasks import Task
from app.models.workflow import ApprovalRequest, ApprovalStatus


def apply_approval(db: Session, approval: ApprovalRequest) -> None:
    """Mutate the target entity to reflect an approved decision.

    No-op if rejected or target type has no registered handler.
    """
    if approval.status != ApprovalStatus.approved:
        return

    handlers = {
        "scope_item":              _apply_scope_item,
        "evidence_request_waiver": _apply_er_waiver,
        "task_cancellation":       _apply_task_cancel,
    }
    handler = handlers.get(approval.target_type)
    if handler:
        handler(db, approval)


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
