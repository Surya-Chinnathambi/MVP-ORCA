"""Admin pack-management endpoints.

Register packs from disk, manage their lifecycle, diff versions.
All lifecycle transitions route through the approval gateway.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.methodology import MethodologyPack, PackLifecycle
from app.models.users import User
from app.services.packs.registry import (
    active_pack_for_key,
    apply_approved_transition,
    load_pack_from_db,
    register_pack,
    request_lifecycle_transition,
)

router = APIRouter(prefix="/packs", tags=["packs"])


class RegisterPackIn(BaseModel):
    pack_key: str
    version: str = "1.0.0"
    organization_id: Optional[str] = None


class TransitionIn(BaseModel):
    to_lifecycle: PackLifecycle
    reason: str = ""


class ApproveTransitionIn(BaseModel):
    approved: bool
    reason: Optional[str] = None


def _pack_out(mp: MethodologyPack) -> Dict[str, Any]:
    return {
        "id": mp.id,
        "key": mp.key,
        "title": mp.title,
        "version": mp.version,
        "lifecycle": mp.lifecycle,
        "checksum": mp.checksum,
        "approved_by": mp.approved_by,
        "approved_at": mp.approved_at.isoformat() if mp.approved_at else None,
        "created_at": mp.created_at.isoformat(),
    }


@router.post("", status_code=201)
def register(
    body: RegisterPackIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Register an on-disk pack as a draft MethodologyPack."""
    try:
        mp = register_pack(
            db,
            body.pack_key,
            version=body.version,
            organization_id=body.organization_id,
            actor_id=current_user.id,
        )
        db.commit()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _pack_out(mp)


@router.get("", response_model=List[Dict[str, Any]])
def list_packs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all registered MethodologyPacks."""
    return [_pack_out(mp) for mp in db.query(MethodologyPack).order_by(MethodologyPack.created_at).all()]


@router.get("/{pack_id}")
def get_pack(
    pack_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a MethodologyPack record including its source_json."""
    mp = db.get(MethodologyPack, pack_id)
    if mp is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    out = _pack_out(mp)
    out["source_json"] = mp.source_json
    return out


@router.post("/{pack_id}/transition")
def transition(
    pack_id: str,
    body: TransitionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Request a lifecycle transition.

    Returns the pack plus an `approval_id` if the transition needs approval.
    """
    try:
        mp, approval = request_lifecycle_transition(
            db,
            pack_id,
            to_lifecycle=body.to_lifecycle,
            actor_id=current_user.id,
            reason=body.reason,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    out = _pack_out(mp)
    out["approval_id"] = approval.id if approval else None
    return out


@router.post("/{pack_id}/approve/{approval_id}")
def approve_transition(
    pack_id: str,
    approval_id: str,
    body: ApproveTransitionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Resolve a pending pack lifecycle approval."""
    try:
        mp = apply_approved_transition(
            db,
            approval_id,
            approved=body.approved,
            decider_id=current_user.id,
            reason=body.reason,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _pack_out(mp)


@router.get("/{pack_id}/diff/{other_pack_id}")
def diff_versions(
    pack_id: str,
    other_pack_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Surface checksum and requirement-count differences between two pack versions."""
    a = db.get(MethodologyPack, pack_id)
    b = db.get(MethodologyPack, other_pack_id)
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="One or both packs not found")
    same = a.checksum == b.checksum
    reqs_a = len((a.source_json or {}).get("requirements", []))
    reqs_b = len((b.source_json or {}).get("requirements", []))
    return {
        "pack_a": {"id": a.id, "version": a.version, "checksum": a.checksum, "requirements": reqs_a},
        "pack_b": {"id": b.id, "version": b.version, "checksum": b.checksum, "requirements": reqs_b},
        "identical": same,
        "requirements_delta": reqs_b - reqs_a,
    }
