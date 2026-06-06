"""Methodology API — plan generation driven by DB-pinned MethodologyPacks.

The disk-based routes (GET /methodology/packs, GET /methodology/packs/{key})
are preserved as seed-pack browsing endpoints ("which packs are available to register").
Plan generation reads from the DB-pinned version; for backward compatibility with
pre-Stage-16 projects whose pack_id is a short key string, it falls back to disk.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.methodology import PackLifecycle
from app.models.users import User
from app.services.methodology.loader import available_packs, load_pack
from app.services.methodology.plan import generate_plan
from app.services.packs.registry import load_pack_from_db

router = APIRouter(prefix="/methodology", tags=["methodology"])


class AttachPackIn(BaseModel):
    pack_id: str


# ── Seed-pack browsing (on-disk, pre-registration) ────────────────────────────

@router.get("/packs", response_model=List[str])
def list_seed_packs(_: User = Depends(get_current_user)):
    """Return keys of seed packs available on disk for registration."""
    return available_packs()


@router.get("/packs/{pack_key}")
def get_seed_pack(pack_key: str, _: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Return the full pack definition from the on-disk seed file."""
    try:
        pack = load_pack(pack_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Seed pack '{pack_key}' not found")
    return pack.model_dump()


# ── Project plan management ───────────────────────────────────────────────────

@router.post("/projects/{project_id}/attach-pack")
def attach_pack(
    project_id: str,
    body: AttachPackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Attach an active MethodologyPack to a project (version-pins it).

    Only a pack with lifecycle=active may be attached.
    """
    from app.models.methodology import MethodologyPack

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    mp = db.get(MethodologyPack, body.pack_id)
    if mp is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    if mp.lifecycle != PackLifecycle.active.value:
        raise HTTPException(
            status_code=400,
            detail=f"Only active packs may be attached; this pack is '{mp.lifecycle}'",
        )

    project.pack_id = mp.id
    db.commit()
    return {"project_id": project_id, "pack_id": mp.id, "pack_key": mp.key}


@router.post("/projects/{project_id}/plan")
def generate_project_plan(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate a project plan from the pack.

    Loads from the DB-pinned MethodologyPack (Stage 16+ path).
    Falls back to on-disk loader if pack_id is a legacy string key.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.pack_id:
        raise HTTPException(status_code=400, detail="Project has no pack attached")

    # Try DB-pinned loader first (Stage 16+ path)
    try:
        pack = load_pack_from_db(db, project.pack_id)
        pack_key = pack.key
    except ValueError:
        # Fallback: treat pack_id as a disk key (pre-Stage-16 projects)
        try:
            pack = load_pack(project.pack_id)
            pack_key = pack.key
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Pack '{project.pack_id}' not found")

    summary = generate_plan(db, project, pack)
    db.commit()
    return {
        "project_id": project_id,
        "pack_id": project.pack_id,
        "pack_key": pack_key,
        "requirements_created": summary.requirements_created,
        "evidence_requests_created": summary.evidence_requests_created,
        "tasks_created": summary.tasks_created,
    }
