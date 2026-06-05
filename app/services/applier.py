"""Apply the outcome of a decided approval to its target entity.

Stage 3 handles scope_item only.
Stage 8 expands this dispatcher to all controlled target types.
"""
from sqlalchemy.orm import Session

from app.models.scope import ScopeItem
from app.models.workflow import ApprovalRequest, ApprovalStatus


def apply_approval(db: Session, approval: ApprovalRequest) -> None:
    """Mutate the target entity to reflect an approved decision.

    Called immediately after decide_approval(); no-op if rejected or
    target type is not yet handled.
    """
    if approval.status != ApprovalStatus.approved:
        return

    handlers = {
        "scope_item": _apply_scope_item,
    }
    handler = handlers.get(approval.target_type)
    if handler:
        handler(db, approval)


def _apply_scope_item(db: Session, approval: ApprovalRequest) -> None:
    item = db.get(ScopeItem, approval.target_id)
    if item:
        item.approved = True
