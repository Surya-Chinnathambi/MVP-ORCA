"""Evidence internal lifecycle service (Stage 18).

Dual-track: the user-facing reviewer_status (pending|accepted|rejected) exists
alongside the internal internal_lifecycle_state
(intake→verified→classified→packaged→delivered→archived).

Allowed transitions:
  intake     → verified    (verify_evidence — reviewer action)
  verified   → classified  (classify_evidence — reviewer action; requires classification set)
  classified → packaged    (package_evidence — deliverable action; gated by state=classified)
  packaged   → delivered   (deliver_evidence — fires on deliverable release)
  delivered  → archived    (archive_evidence)

supersede_evidence() creates a replacement item that retains the old item in the DB
with supersedes_id pointing back to it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evidence import (
    EvidenceItem,
    EvidenceLifecycleEvent,
    EvidenceLifecycleState,
    ReviewerStatus,
)


# ── Transition table ──────────────────────────────────────────────────────────

_ALLOWED: dict[str, str] = {
    EvidenceLifecycleState.intake.value:      EvidenceLifecycleState.verified.value,
    EvidenceLifecycleState.verified.value:    EvidenceLifecycleState.classified.value,
    EvidenceLifecycleState.classified.value:  EvidenceLifecycleState.packaged.value,
    EvidenceLifecycleState.packaged.value:    EvidenceLifecycleState.delivered.value,
    EvidenceLifecycleState.delivered.value:   EvidenceLifecycleState.archived.value,
}


def _transition(
    db: Session,
    item: EvidenceItem,
    expected_from: str,
    to_state: str,
    actor_id: Optional[str],
    reason: Optional[str] = None,
) -> None:
    if item.internal_lifecycle_state != expected_from:
        raise ValueError(
            f"EvidenceItem {item.id!r} is in state {item.internal_lifecycle_state!r}; "
            f"cannot transition to {to_state!r} (expected from {expected_from!r})"
        )
    event = EvidenceLifecycleEvent(
        evidence_item_id=item.id,
        from_state=expected_from,
        to_state=to_state,
        actor_id=actor_id,
        reason=reason,
    )
    db.add(event)
    item.internal_lifecycle_state = to_state


def _get_or_raise(db: Session, item_id: str) -> EvidenceItem:
    item = db.get(EvidenceItem, item_id)
    if item is None:
        raise ValueError(f"EvidenceItem {item_id!r} not found")
    return item


# ── Public transitions ────────────────────────────────────────────────────────

def verify_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """intake → verified. Also sets reviewer_status=accepted."""
    item = _get_or_raise(db, evidence_item_id)
    _transition(db, item, EvidenceLifecycleState.intake.value, EvidenceLifecycleState.verified.value, actor_id, reason)
    item.reviewer_status = ReviewerStatus.accepted.value
    return item


def classify_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """verified → classified. Item must already have a classification value."""
    item = _get_or_raise(db, evidence_item_id)
    if not item.classification:
        raise ValueError(
            f"EvidenceItem {item.id!r} has no classification set; "
            "run keyword classification before classifying"
        )
    _transition(db, item, EvidenceLifecycleState.verified.value, EvidenceLifecycleState.classified.value, actor_id, reason)
    return item


def package_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """classified → packaged (deliverable action).

    GATED: item must be in 'classified' state (which implies it is verified+classified).
    """
    item = _get_or_raise(db, evidence_item_id)
    _transition(db, item, EvidenceLifecycleState.classified.value, EvidenceLifecycleState.packaged.value, actor_id, reason)
    return item


def deliver_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """packaged → delivered (fires when deliverable is released)."""
    item = _get_or_raise(db, evidence_item_id)
    _transition(db, item, EvidenceLifecycleState.packaged.value, EvidenceLifecycleState.delivered.value, actor_id, reason)
    return item


def archive_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """delivered → archived."""
    item = _get_or_raise(db, evidence_item_id)
    _transition(db, item, EvidenceLifecycleState.delivered.value, EvidenceLifecycleState.archived.value, actor_id, reason)
    return item


# ── Bulk release helper ───────────────────────────────────────────────────────

def mark_project_evidence_delivered(
    db: Session,
    project_id: str,
    actor_id: Optional[str] = None,
) -> int:
    """Promote all packaged evidence items for a project to delivered.

    Called by the deliverable release path (Gate 6).
    Returns the count of items promoted.
    """
    items = (
        db.query(EvidenceItem)
        .filter_by(project_id=project_id, internal_lifecycle_state=EvidenceLifecycleState.packaged.value)
        .all()
    )
    for item in items:
        _transition(db, item, EvidenceLifecycleState.packaged.value, EvidenceLifecycleState.delivered.value, actor_id, "deliverable released")
    return len(items)


# ── Supersede chain ───────────────────────────────────────────────────────────

def supersede_evidence(
    db: Session,
    old_item_id: str,
    *,
    project_id: str,
    data: bytes,
    filename: str,
    actor_id: Optional[str] = None,
) -> EvidenceItem:
    """Create a replacement EvidenceItem that supersedes old_item_id.

    The old item is retained (not deleted). The new item:
    - has supersedes_id = old_item_id
    - inherits evidence_request_id from the old item
    - starts at internal_lifecycle_state=intake
    """
    from app.services.evidence.ingest import ingest_file

    old_item = _get_or_raise(db, old_item_id)
    new_item = ingest_file(
        db,
        project_id=project_id,
        data=data,
        filename=filename,
        evidence_request_id=old_item.evidence_request_id,
        uploaded_by_id=actor_id,
    )
    new_item.supersedes_id = old_item_id
    return new_item
