"""Scope Builder — every mutation routes through the approval gateway (Gate 1)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.scope import ScopeItem
from app.models.users import User
from app.schemas.scope import ScopeItemCreate, ScopeItemOut, ScopeItemUpdate
from app.schemas.approvals import ApprovalOut
from app.services.audit import record_event, request_approval

router = APIRouter(prefix="/projects/{project_id}/scope", tags=["scope"])


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/", response_model=List[ScopeItemOut])
def list_scope(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _get_project_or_404(project_id, db)
    return db.query(ScopeItem).filter_by(project_id=project_id).all()


@router.post("/", response_model=ApprovalOut, status_code=status.HTTP_201_CREATED)
def add_scope_item(
    project_id: str,
    body: ScopeItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a scope item. Returns the pending ApprovalRequest — must be approved
    before scope_item.approved flips True (Gate 1)."""
    _get_project_or_404(project_id, db)
    item = ScopeItem(project_id=project_id, kind=body.kind, value=body.value, approved=False)
    db.add(item)
    db.flush()   # populate item.id before passing to gateway

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="scope_item",
        target_id=item.id,
        reason=body.reason or f"Add {body.kind}: {body.value}",
        approver_role="reviewer",
        change_before=None,
        change_after={"kind": body.kind, "value": body.value},
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.patch("/{item_id}", response_model=ApprovalOut)
def update_scope_item(
    project_id: str,
    item_id: str,
    body: ScopeItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit a scope item value. Change is held pending approval."""
    _get_project_or_404(project_id, db)
    item = db.get(ScopeItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scope item not found")

    before = {"kind": item.kind, "value": item.value}
    after = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k != "reason"}

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="scope_item",
        target_id=item_id,
        reason=body.reason or f"Edit scope item {item_id}",
        approver_role="reviewer",
        change_before=before,
        change_after=after,
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.delete("/{item_id}", response_model=ApprovalOut)
def remove_scope_item(
    project_id: str,
    item_id: str,
    reason: str = "Remove scope item",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request removal of a scope item — requires approval before deletion."""
    _get_project_or_404(project_id, db)
    item = db.get(ScopeItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scope item not found")

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="scope_item_removal",
        target_id=item_id,
        reason=reason,
        approver_role="reviewer",
        change_before={"kind": item.kind, "value": item.value},
        change_after=None,
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval
