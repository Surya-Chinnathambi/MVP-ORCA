"""Methodology API — load packs and generate project plans."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.users import User
from app.services.methodology.loader import available_packs, load_pack
from app.services.methodology.plan import generate_plan

router = APIRouter(prefix="/methodology", tags=["methodology"])


@router.get("/packs", response_model=List[str])
def list_packs(_: User = Depends(get_current_user)):
    """Return available pack keys."""
    return available_packs()


@router.get("/packs/{pack_key}")
def get_pack(pack_key: str, _: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Return the full pack definition."""
    try:
        pack = load_pack(pack_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Pack '{pack_key}' not found")
    return pack.model_dump()


@router.post("/projects/{project_id}/plan")
def generate_project_plan(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate plan for a project from its pack_id.

    Idempotent — safe to call multiple times; existing rows are skipped.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pack_id:
        raise HTTPException(status_code=400, detail="Project has no pack_id set")

    try:
        pack = load_pack(project.pack_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Pack '{project.pack_id}' not found")

    summary = generate_plan(db, project, pack)
    db.commit()
    return {
        "project_id": project_id,
        "pack_key": pack.key,
        "requirements_created": summary.requirements_created,
        "evidence_requests_created": summary.evidence_requests_created,
        "tasks_created": summary.tasks_created,
    }
