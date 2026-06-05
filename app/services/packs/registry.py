"""Pack registry — register, lifecycle-manage, and load MethodologyPacks from DB.

On-disk pack.json files are the *seed source* only.
Once registered, the DB version is the authoritative runtime source.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.methodology import MethodologyPack, PackLifecycle
from app.models.workflow import ApprovalRequest
from app.services.audit import decide_approval, record_event, request_approval
from app.services.methodology.loader import Pack, load_pack

# Lifecycle transitions allowed from each state
_ALLOWED_NEXT: dict[PackLifecycle, list[PackLifecycle]] = {
    PackLifecycle.draft: [PackLifecycle.internal_review],
    PackLifecycle.internal_review: [PackLifecycle.approved, PackLifecycle.draft],
    PackLifecycle.approved: [PackLifecycle.active, PackLifecycle.draft],
    PackLifecycle.active: [PackLifecycle.deprecated],
    PackLifecycle.deprecated: [PackLifecycle.archived],
    PackLifecycle.archived: [],
}

# Transitions that require an ApprovalRequest (human sign-off)
_APPROVAL_REQUIRED: set[PackLifecycle] = {PackLifecycle.approved, PackLifecycle.active}

# Which approver role guards each gated transition
_APPROVER_ROLE: dict[PackLifecycle, str] = {
    PackLifecycle.approved: "qa",
    PackLifecycle.active: "admin",
}


def _checksum(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


# ── Registration ──────────────────────────────────────────────────────────────

def register_pack(
    db: Session,
    pack_key: str,
    *,
    version: str = "1.0.0",
    organization_id: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> MethodologyPack:
    """Load an on-disk pack.json, validate it, and store as a draft MethodologyPack.

    Multiple versions of the same key may coexist; lifecycle governs which is active.
    """
    pack = load_pack(pack_key)
    data = pack.model_dump()
    cs = _checksum(data)

    mp = MethodologyPack(
        organization_id=organization_id,
        key=pack.key,
        title=pack.title,
        version=version,
        lifecycle=PackLifecycle.draft,
        source_json=data,
        checksum=cs,
    )
    db.add(mp)
    db.flush()
    record_event(
        db,
        action="pack.registered",
        target_type="methodology_pack",
        target_id=mp.id,
        actor_id=actor_id,
        after={"key": mp.key, "version": mp.version, "lifecycle": mp.lifecycle},
    )
    return mp


# ── Lifecycle transitions ─────────────────────────────────────────────────────

def request_lifecycle_transition(
    db: Session,
    pack_id: str,
    *,
    to_lifecycle: PackLifecycle,
    actor_id: str,
    reason: str = "",
) -> tuple[MethodologyPack, Optional[ApprovalRequest]]:
    """Request a lifecycle transition.

    If the target state requires an approval, an ApprovalRequest (pending) is
    created and returned; the pack lifecycle is NOT changed yet.
    Otherwise the transition is applied immediately and None is returned for
    the approval.
    """
    mp = db.get(MethodologyPack, pack_id)
    if mp is None:
        raise ValueError(f"MethodologyPack {pack_id!r} not found")

    current = PackLifecycle(mp.lifecycle)
    allowed = _ALLOWED_NEXT.get(current, [])
    if to_lifecycle not in allowed:
        raise ValueError(
            f"Cannot transition {current.value!r} → {to_lifecycle.value!r}; "
            f"allowed next: {[s.value for s in allowed]}"
        )

    if to_lifecycle in _APPROVAL_REQUIRED:
        approval = request_approval(
            db,
            project_id=None,
            target_type="methodology_pack",
            target_id=mp.id,
            reason=reason or f"Pack {mp.key!r} lifecycle: {current.value} → {to_lifecycle.value}",
            approver_role=_APPROVER_ROLE[to_lifecycle],
            change_before={"lifecycle": current.value},
            change_after={"lifecycle": to_lifecycle.value},
            requested_by=actor_id,
        )
        return mp, approval
    else:
        old = mp.lifecycle
        mp.lifecycle = to_lifecycle.value
        record_event(
            db,
            action=f"pack.lifecycle.{to_lifecycle.value}",
            target_type="methodology_pack",
            target_id=mp.id,
            actor_id=actor_id,
            before={"lifecycle": old},
            after={"lifecycle": to_lifecycle.value},
            reason=reason,
        )
        return mp, None


def apply_approved_transition(
    db: Session,
    approval_id: str,
    *,
    approved: bool,
    decider_id: str,
    reason: Optional[str] = None,
) -> MethodologyPack:
    """Resolve a pending pack-lifecycle ApprovalRequest and apply the transition."""
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise ValueError(f"ApprovalRequest {approval_id!r} not found")

    mp = db.get(MethodologyPack, approval.target_id)
    if mp is None:
        raise ValueError(f"MethodologyPack {approval.target_id!r} not found")

    decide_approval(
        db, approval_id=approval_id, approved=approved,
        decider_id=decider_id, reason=reason,
    )

    if approved:
        new_lifecycle = PackLifecycle(approval.change_after["lifecycle"])
        old = mp.lifecycle
        mp.lifecycle = new_lifecycle.value
        if new_lifecycle == PackLifecycle.approved:
            mp.approved_by = decider_id
            mp.approved_at = datetime.now(timezone.utc)
        record_event(
            db,
            action=f"pack.lifecycle.{new_lifecycle.value}",
            target_type="methodology_pack",
            target_id=mp.id,
            actor_id=decider_id,
            before={"lifecycle": old},
            after={"lifecycle": new_lifecycle.value},
            reason=reason,
        )
    return mp


# ── DB loader (replaces disk loader for runtime use) ─────────────────────────

def load_pack_from_db(db: Session, pack_id: str) -> Pack:
    """Load the Pack schema object from the DB version-pinned source_json."""
    mp = db.get(MethodologyPack, pack_id)
    if mp is None:
        raise ValueError(f"MethodologyPack {pack_id!r} not found")
    return Pack.model_validate(mp.source_json)


def active_pack_for_key(db: Session, key: str) -> Optional[MethodologyPack]:
    """Return the active MethodologyPack for a given key, or None."""
    return (
        db.query(MethodologyPack)
        .filter_by(key=key, lifecycle=PackLifecycle.active.value)
        .first()
    )
