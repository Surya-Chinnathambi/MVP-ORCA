from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.users import User
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.schemas.approvals import ApprovalDecide, ApprovalOut
from app.services.audit import decide_approval
from app.services.applier import apply_approval

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/", response_model=List[ApprovalOut])
def list_approvals(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(ApprovalRequest)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    return q.all()


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    a = db.get(ApprovalRequest, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return a


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
def decide(
    approval_id: str,
    body: ApprovalDecide,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a pending request, then apply the change to its target."""
    try:
        approval = decide_approval(
            db,
            approval_id=approval_id,
            approved=body.approved,
            decider_id=current_user.id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    apply_approval(db, approval)
    db.commit()
    db.refresh(approval)
    return approval
