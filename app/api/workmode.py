"""Work mode API — context resolution, last-active context persistence."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.deps import get_current_user
from app.models.users import User
from app.models.workmode import WorkMode
from app.services.context_resolver import (
    persist_last_context,
    resolve_context,
    restore_last_context,
    seed_work_modes,
)

router = APIRouter(tags=["work-modes"])


class ResolveContextRequest(BaseModel):
    project_id: str
    work_mode_name: str


class LastContextUpdate(BaseModel):
    project_id: Optional[str] = None
    client_id: Optional[str] = None
    work_mode_name: Optional[str] = None


# ── List available modes ──────────────────────────────────────────────────────

@router.get("/work-modes")
def list_work_modes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all configured work modes with allowed_views and default_filters."""
    modes = db.query(WorkMode).order_by(WorkMode.name).all()
    return [
        {
            "name": m.name,
            "display_name": m.display_name,
            "allowed_views": m.allowed_views,
            "default_filters": m.default_filters,
        }
        for m in modes
    ]


# ── Resolve context ───────────────────────────────────────────────────────────

@router.post("/work-modes/resolve-context")
def resolve_context_endpoint(
    body: ResolveContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve the project context scoped to the requested work mode."""
    try:
        ctx = resolve_context(db, current_user.id, body.project_id, body.work_mode_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist as last-active
    persist_last_context(
        db,
        current_user.id,
        project_id=body.project_id,
        work_mode_name=body.work_mode_name,
    )
    db.commit()
    return ctx


# ── Last-active context ───────────────────────────────────────────────────────

@router.get("/users/me/last-context")
def get_last_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the last-active context for the authenticated user."""
    record = restore_last_context(db, current_user.id)
    if record is None:
        return {}
    return record


@router.put("/users/me/last-context")
def update_last_context(
    body: LastContextUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the last-active context (partial update — only non-None fields)."""
    record = persist_last_context(
        db,
        current_user.id,
        project_id=body.project_id,
        client_id=body.client_id,
        work_mode_name=body.work_mode_name,
    )
    db.commit()
    return restore_last_context(db, current_user.id)


# ── Seed ──────────────────────────────────────────────────────────────────────

@router.post("/work-modes/seed", include_in_schema=False)
def seed_modes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Insert any missing default WorkMode rows."""
    count = seed_work_modes(db)
    db.commit()
    return {"inserted": count}
