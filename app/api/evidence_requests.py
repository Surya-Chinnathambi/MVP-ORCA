"""Evidence-request tracker — status open|received|waived (waive via gateway)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.users import User
from app.schemas.approvals import ApprovalOut
from app.schemas.evidence_requests import (
    EvidenceRequestCreate,
    EvidenceRequestOut,
    EvidenceRequestUpdate,
    WaiveRequest,
)
from app.services.audit import request_approval

router = APIRouter(
    prefix="/projects/{project_id}/evidence-requests",
    tags=["evidence-requests"],
)


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("/", response_model=List[EvidenceRequestOut])
def list_evidence_requests(
    project_id: str,
    status: Optional[str] = None,
    requirement_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    q = db.query(EvidenceRequest).filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if requirement_id:
        q = q.filter_by(requirement_id=requirement_id)
    return q.all()


@router.post("/", response_model=EvidenceRequestOut, status_code=status.HTTP_201_CREATED)
def create_evidence_request(
    project_id: str,
    body: EvidenceRequestCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    er = EvidenceRequest(
        project_id=project_id,
        requirement_id=body.requirement_id,
        title=body.title,
        description=body.description,
        status=EvidenceRequestStatus.open,
        owner_id=body.owner_id,
        due_date=body.due_date,
    )
    db.add(er)
    db.commit()
    db.refresh(er)
    return er


@router.get("/{er_id}", response_model=EvidenceRequestOut)
def get_evidence_request(
    project_id: str,
    er_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    er = db.get(EvidenceRequest, er_id)
    if er is None or er.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence request not found")
    return er


@router.patch("/{er_id}", response_model=EvidenceRequestOut)
def update_evidence_request(
    project_id: str,
    er_id: str,
    body: EvidenceRequestUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Update title/description/owner/due_date or mark as received.
    Use /waive to request waiver — that goes through the approval gateway."""
    _project_or_404(project_id, db)
    er = db.get(EvidenceRequest, er_id)
    if er is None or er.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence request not found")
    if body.status == EvidenceRequestStatus.waived:
        raise HTTPException(
            status_code=400,
            detail="Use POST /waive to request a waiver — approval required",
        )
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(er, field, val)
    db.commit()
    db.refresh(er)
    return er


@router.post("/{er_id}/waive", response_model=ApprovalOut)
def waive_evidence_request(
    project_id: str,
    er_id: str,
    body: WaiveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request a waiver for this evidence request.
    Status flips to 'waived' only after the returned approval is approved."""
    _project_or_404(project_id, db)
    er = db.get(EvidenceRequest, er_id)
    if er is None or er.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence request not found")
    if er.status == EvidenceRequestStatus.waived:
        raise HTTPException(status_code=400, detail="Evidence request is already waived")

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="evidence_request_waiver",
        target_id=er_id,
        reason=body.reason,
        approver_role="reviewer",
        change_before={"status": er.status},
        change_after={"status": "waived"},
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval
