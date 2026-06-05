"""Controlled evidence export (Stage 20).

export_evidence() gates restricted-evidence access behind an evidence_item
scope-level Permission, writes an AuditTrailEvent, and returns the file path.

Raises PermissionError if the requesting user lacks the evidence_item permission
for restricted items.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem
from app.models.users import Permission, Role, ScopeLevel, User
from app.services.audit import record_event

_EVIDENCE_ROOT = Path("data/evidence")


def _has_evidence_item_permission(db: Session, user_id: str, item_id: str) -> bool:
    """Return True if user has an evidence_item-scoped (or broader) permission."""
    # Acceptable scope levels for restricted evidence access
    ALLOWED_SCOPES = {ScopeLevel.evidence_item.value, ScopeLevel.organization.value}
    perms = (
        db.query(Permission)
        .filter(
            Permission.user_id == user_id,
            Permission.scope_level.in_(ALLOWED_SCOPES),
        )
        .all()
    )
    for perm in perms:
        # scope_id==None means org-wide; scope_id==item_id means item-specific
        if perm.scope_id is None or perm.scope_id == item_id:
            return True
    return False


def export_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: str,
    output_path: Optional[Path] = None,
) -> Path:
    """Gate-check then return the stored file path for the evidence item.

    Writes an AuditTrailEvent regardless of outcome (success or blocked).
    Raises PermissionError if item is restricted and user lacks evidence_item scope.
    """
    item = db.get(EvidenceItem, evidence_item_id)
    if item is None:
        raise ValueError(f"EvidenceItem {evidence_item_id!r} not found")

    if item.is_restricted and not _has_evidence_item_permission(db, actor_id, evidence_item_id):
        record_event(
            db,
            action="evidence.export.blocked",
            target_type="evidence_item",
            target_id=evidence_item_id,
            actor_id=actor_id,
            project_id=item.project_id,
            after={"reason": "missing evidence_item permission"},
        )
        db.flush()
        raise PermissionError(
            f"User {actor_id!r} lacks evidence_item permission for restricted item {evidence_item_id!r}"
        )

    src_path = _EVIDENCE_ROOT / item.project_id / f"{item.sha256}{Path(item.source_file).suffix}"

    record_event(
        db,
        action="evidence.export.success",
        target_type="evidence_item",
        target_id=evidence_item_id,
        actor_id=actor_id,
        project_id=item.project_id,
        after={"exported_path": str(src_path)},
    )
    db.flush()
    return src_path
