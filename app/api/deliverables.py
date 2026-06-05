"""Deliverables API — generate gap matrix, roadmap, and report; manage release."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.users import User
from app.models.workflow import ApprovalStatus
from app.schemas.deliverables import DeliverableOut, ReleaseRequest
from app.services.audit import record_event, request_approval
from app.services.deliverables.gap_matrix import generate_gap_matrix
from app.services.deliverables.report import generate_report, has_release_approval
from app.services.deliverables.roadmap import generate_roadmap

router = APIRouter(
    prefix="/projects/{project_id}/deliverables",
    tags=["deliverables"],
)

_BASE_DATA = Path("data/deliverables")


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[DeliverableOut])
def list_deliverables(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    return (
        db.query(Deliverable)
        .filter_by(project_id=project_id)
        .order_by(Deliverable.kind, Deliverable.version.desc())
        .all()
    )


# ── Generate ──────────────────────────────────────────────────────────────────

@router.post("/gap-matrix", response_model=list[DeliverableOut], status_code=201)
def create_gap_matrix(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db)
    out_dir = _BASE_DATA / project_id / "gap_matrix"
    xlsx_del, html_del = generate_gap_matrix(db, project, out_dir, current_user.id)
    record_event(
        db,
        action="deliverable.generated.gap_matrix",
        target_type="deliverable",
        target_id=xlsx_del.id,
        actor_id=current_user.id,
        project_id=project_id,
        after={"version": xlsx_del.version, "format": "xlsx+html"},
    )
    db.commit()
    db.refresh(xlsx_del)
    db.refresh(html_del)
    return [xlsx_del, html_del]


@router.post("/roadmap", response_model=list[DeliverableOut], status_code=201)
def create_roadmap(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db)
    out_dir = _BASE_DATA / project_id / "roadmap"
    md_del, html_del = generate_roadmap(db, project, out_dir, current_user.id)
    record_event(
        db,
        action="deliverable.generated.roadmap",
        target_type="deliverable",
        target_id=md_del.id,
        actor_id=current_user.id,
        project_id=project_id,
        after={"version": md_del.version, "format": "md+html"},
    )
    db.commit()
    db.refresh(md_del)
    db.refresh(html_del)
    return [md_del, html_del]


@router.post("/report", response_model=DeliverableOut, status_code=201)
def create_report(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db)
    out_dir = _BASE_DATA / project_id / "report"
    deliverable = generate_report(db, project, out_dir, current_user.id)
    record_event(
        db,
        action="deliverable.generated.report",
        target_type="deliverable",
        target_id=deliverable.id,
        actor_id=current_user.id,
        project_id=project_id,
        after={"version": deliverable.version, "format": "html"},
    )
    db.commit()
    db.refresh(deliverable)
    return deliverable


# ── Release (Gate 6 — requires approval) ─────────────────────────────────────

@router.post("/{deliverable_id}/request-release", response_model=dict)
def request_report_release(
    project_id: str,
    deliverable_id: str,
    body: ReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an approval request for releasing this deliverable (Gate 6)."""
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None or deliverable.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    if deliverable.kind != DeliverableKind.report:
        raise HTTPException(status_code=400, detail="Only reports require release approval")

    approval = request_approval(
        db,
        project_id=project_id,
        target_type="deliverable",
        target_id=deliverable_id,
        reason=body.reason,
        approver_role="partner",
        change_before={"released": False},
        change_after={"released": True},
        requested_by=current_user.id,
    )
    db.commit()
    return {"approval_id": approval.id, "status": approval.status}


@router.post("/{deliverable_id}/release", response_model=DeliverableOut)
def release_deliverable(
    project_id: str,
    deliverable_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a report as released — only succeeds if a release approval exists."""
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None or deliverable.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    if deliverable.kind != DeliverableKind.report:
        raise HTTPException(status_code=400, detail="Only reports can be released")

    if not has_release_approval(db, deliverable_id):
        raise HTTPException(
            status_code=403,
            detail="Report release requires an approved ApprovalRequest (Gate 6). "
                   "Use /request-release first.",
        )

    from datetime import datetime, timezone
    record_event(
        db,
        action="deliverable.released",
        target_type="deliverable",
        target_id=deliverable_id,
        actor_id=current_user.id,
        project_id=project_id,
        before={"released": False},
        after={"released": True},
    )
    # Mark project gate G6 if not already set
    project = _project_or_404(project_id, db)
    gates = dict(project.gates or {})
    if not gates.get("G6_report"):
        gates["G6_report"] = True
        project.gates = gates

    db.commit()
    db.refresh(deliverable)
    return deliverable
