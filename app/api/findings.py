"""Findings Register — create, filter, attach evidence, gated severity/status changes."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.tasks import Finding
from app.models.users import User
from app.schemas.approvals import ApprovalOut
from app.schemas.findings import (
    ChangeSeverity,
    ChangeStatus,
    FindingCreate,
    FindingOut,
    FindingUpdate,
)
from app.services.audit import record_event, request_approval

router = APIRouter(prefix="/projects/{project_id}/findings", tags=["findings"])


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _finding_or_404(project_id: str, finding_id: str, db: Session) -> Finding:
    f = db.get(Finding, finding_id)
    if f is None or f.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    return f


@router.get("/", response_model=List[FindingOut])
def list_findings(
    project_id: str,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    requirement_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    q = db.query(Finding).filter_by(project_id=project_id)
    if severity:
        q = q.filter_by(severity=severity)
    if status:
        q = q.filter_by(status=status)
    if source:
        q = q.filter_by(source=source)
    if requirement_id:
        q = q.filter_by(requirement_id=requirement_id)
    return q.order_by(Finding.created_at.desc()).all()


@router.post("/", response_model=FindingOut, status_code=status.HTTP_201_CREATED)
def create_finding(
    project_id: str,
    body: FindingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    finding = Finding(
        project_id=project_id,
        title=body.title,
        description=body.description,
        severity=body.severity,
        status="open",
        requirement_id=body.requirement_id,
        evidence_item_ids=body.evidence_item_ids or [],
        source=body.source,
        owner_id=body.owner_id,
    )
    db.add(finding)
    db.flush()
    record_event(
        db,
        action="finding.created",
        target_type="finding",
        target_id=finding.id,
        actor_id=current_user.id,
        project_id=project_id,
        after={"title": finding.title, "severity": finding.severity, "source": finding.source},
    )
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/{finding_id}", response_model=FindingOut)
def get_finding(
    project_id: str,
    finding_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    return _finding_or_404(project_id, finding_id, db)


@router.patch("/{finding_id}", response_model=FindingOut)
def update_finding(
    project_id: str,
    finding_id: str,
    body: FindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update non-gated fields (title, description, owner, evidence_item_ids).
    Use /change-severity and /change-status for approval-gated changes."""
    _project_or_404(project_id, db)
    finding = _finding_or_404(project_id, finding_id, db)
    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(finding, k) for k in updates}
    for field, val in updates.items():
        setattr(finding, field, val)
    record_event(
        db,
        action="finding.updated",
        target_type="finding",
        target_id=finding_id,
        actor_id=current_user.id,
        project_id=project_id,
        before=before,
        after=updates,
    )
    db.commit()
    db.refresh(finding)
    return finding


@router.post("/{finding_id}/change-severity", response_model=ApprovalOut)
def change_severity(
    project_id: str,
    finding_id: str,
    body: ChangeSeverity,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request a severity change — always routed through the approval gateway."""
    _project_or_404(project_id, db)
    finding = _finding_or_404(project_id, finding_id, db)
    if finding.severity == body.severity:
        raise HTTPException(status_code=400, detail="Severity is already that value")

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="finding_severity_change",
        target_id=finding_id,
        reason=body.reason,
        approver_role="reviewer",
        change_before={"severity": finding.severity},
        change_after={"severity": body.severity},
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/{finding_id}/change-status", response_model=ApprovalOut)
def change_status(
    project_id: str,
    finding_id: str,
    body: ChangeStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request a status change — always routed through the approval gateway."""
    _project_or_404(project_id, db)
    finding = _finding_or_404(project_id, finding_id, db)
    if finding.status == body.status:
        raise HTTPException(status_code=400, detail="Status is already that value")

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="finding_status_change",
        target_id=finding_id,
        reason=body.reason,
        approver_role="reviewer",
        change_before={"status": finding.status},
        change_after={"status": body.status},
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval
