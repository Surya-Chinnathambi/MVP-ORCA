"""Evidence Items — upload, list, link, reviewer accept/reject."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.evidence import EvidenceItem, EvidenceRequest, ReviewerStatus
from app.models.users import User
from app.schemas.approvals import ApprovalOut
from app.schemas.evidence_items import EvidenceItemLink, EvidenceItemOut, ReviewDecide
from app.services.audit import record_event, request_approval
from app.services.evidence.ingest import ingest_file
from app.services.evidence.manifest import append_item

router = APIRouter(prefix="/projects/{project_id}/evidence-items", tags=["evidence-items"])


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _item_or_404(project_id: str, item_id: str, db: Session) -> EvidenceItem:
    item = db.get(EvidenceItem, item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    return item


@router.post("/upload", response_model=EvidenceItemOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    project_id: str,
    file: UploadFile = File(...),
    evidence_request_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file, extract text, classify, persist as EvidenceItem."""
    _project_or_404(project_id, db)

    if evidence_request_id:
        er = db.get(EvidenceRequest, evidence_request_id)
        if er is None or er.project_id != project_id:
            raise HTTPException(status_code=404, detail="Evidence request not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    item = ingest_file(
        db,
        project_id=project_id,
        data=data,
        filename=file.filename or "upload",
        evidence_request_id=evidence_request_id,
        uploaded_by_id=current_user.id,
    )
    record_event(
        db,
        action="evidence_item.uploaded",
        target_type="evidence_item",
        target_id=item.id,
        actor_id=current_user.id,
        project_id=project_id,
        after={"source_file": item.source_file, "sha256": item.sha256},
    )
    db.commit()
    append_item(project_id, item)
    return item


@router.get("/", response_model=List[EvidenceItemOut])
def list_evidence_items(
    project_id: str,
    reviewer_status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    q = db.query(EvidenceItem).filter_by(project_id=project_id)
    if reviewer_status:
        q = q.filter_by(reviewer_status=reviewer_status)
    return q.all()


@router.get("/{item_id}", response_model=EvidenceItemOut)
def get_evidence_item(
    project_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    return _item_or_404(project_id, item_id, db)


@router.post("/{item_id}/link", response_model=EvidenceItemOut)
def link_evidence_item(
    project_id: str,
    item_id: str,
    body: EvidenceItemLink,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link this item to an evidence request (and its associated requirement)."""
    _project_or_404(project_id, db)
    item = _item_or_404(project_id, item_id, db)
    er = db.get(EvidenceRequest, body.evidence_request_id)
    if er is None or er.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence request not found")

    before = {"evidence_request_id": item.evidence_request_id}
    item.evidence_request_id = body.evidence_request_id
    record_event(
        db,
        action="evidence_item.linked",
        target_type="evidence_item",
        target_id=item_id,
        actor_id=current_user.id,
        project_id=project_id,
        before=before,
        after={"evidence_request_id": body.evidence_request_id},
    )
    db.commit()
    db.refresh(item)
    append_item(project_id, item)
    return item


@router.post("/{item_id}/review")
def review_evidence_item(
    project_id: str,
    item_id: str,
    body: ReviewDecide,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept (direct) or reject (approval-gated) an evidence item.
    Reject returns ApprovalOut; accept returns EvidenceItemOut."""
    _project_or_404(project_id, db)
    item = _item_or_404(project_id, item_id, db)

    if body.accepted:
        item.reviewer_status = ReviewerStatus.accepted
        record_event(
            db,
            action="evidence_item.accepted",
            target_type="evidence_item",
            target_id=item_id,
            actor_id=current_user.id,
            project_id=project_id,
            before={"reviewer_status": "pending"},
            after={"reviewer_status": "accepted"},
            reason=body.reason,
        )
        db.commit()
        db.refresh(item)
        append_item(project_id, item)
        return item

    # Rejection requires approval
    approval = request_approval(
        db,
        project_id=project_id,
        target_type="evidence_rejection",
        target_id=item_id,
        reason=body.reason or "Evidence item rejected by reviewer",
        approver_role="pm",
        change_before={"reviewer_status": item.reviewer_status},
        change_after={"reviewer_status": "rejected"},
        requested_by=current_user.id,
    )
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/manifest/jsonl")
def get_manifest(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the current manifest as a list of records (one per item)."""
    from app.services.evidence.manifest import build_manifest
    import json

    _project_or_404(project_id, db)
    path = build_manifest(db, project_id)
    records = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
