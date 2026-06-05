"""AI agent API endpoints (Stage 23) — advisory only, never mutates directly."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.agent import AgentDraft, DraftStatus
from app.models.users import User
from app.services.agents.base import AgentGuardError

router = APIRouter(prefix="/agents", tags=["agents"])


# ── Request schemas ───────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    evidence_item_id: str
    categories: Optional[list[str]] = None


class DraftFindingRequest(BaseModel):
    project_id: str
    title_hint: str
    description: str


class SummarizeRequest(BaseModel):
    project_id: str
    work_mode: str = "pm"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/classify-evidence", status_code=201)
def classify_evidence(
    body: ClassifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Classify an evidence item into a pack category (draft, not committed)."""
    from app.services.agents.classify import classify_evidence_agent
    try:
        draft = classify_evidence_agent(
            db, body.evidence_item_id, current_user.id, body.categories
        )
        db.commit()
    except (AgentGuardError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"draft_id": draft.id, "status": draft.status, "payload": draft.payload}


@router.post("/draft-finding", status_code=201)
def draft_finding(
    body: DraftFindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Produce a draft finding suggestion (status=draft, severity advisory only)."""
    from app.services.agents.draft_finding import draft_finding_agent
    try:
        draft = draft_finding_agent(
            db, body.project_id, body.title_hint, body.description, current_user.id
        )
        db.commit()
    except AgentGuardError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"draft_id": draft.id, "status": draft.status, "payload": draft.payload}


@router.post("/summarize", status_code=201)
def summarize(
    body: SummarizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Produce a plain-language status summary (draft)."""
    from app.services.agents.summarize import summarize_status_agent
    try:
        draft = summarize_status_agent(
            db, body.project_id, current_user.id, body.work_mode
        )
        db.commit()
    except AgentGuardError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"draft_id": draft.id, "status": draft.status, "payload": draft.payload}


# ── Draft management ──────────────────────────────────────────────────────────

@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    draft = db.get(AgentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {
        "id": draft.id,
        "agent_type": draft.agent_type,
        "status": draft.status,
        "payload": draft.payload,
        "requested_by": draft.requested_by,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


@router.post("/drafts/{draft_id}/accept")
def accept_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Human accepts a draft — marks it accepted. Actual data change is a separate action."""
    draft = db.get(AgentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != DraftStatus.draft.value:
        raise HTTPException(status_code=400, detail="Draft already decided")
    draft.status = DraftStatus.accepted.value
    draft.accepted_by = current_user.id
    db.commit()
    return {"id": draft.id, "status": draft.status}


@router.post("/drafts/{draft_id}/reject")
def reject_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Human rejects a draft."""
    draft = db.get(AgentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != DraftStatus.draft.value:
        raise HTTPException(status_code=400, detail="Draft already decided")
    draft.status = DraftStatus.rejected.value
    db.commit()
    return {"id": draft.id, "status": draft.status}
