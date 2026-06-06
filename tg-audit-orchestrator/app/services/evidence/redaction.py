"""Evidence redaction (Stage 20).

redact_evidence() produces a text-based redacted copy of an EvidenceItem.
The original item is marked is_restricted=True and kept in DB.
The redacted copy is a new EvidenceItem with:
  - source_file prefixed "REDACTED_"
  - extracted_text replaced by a redaction notice
  - classification = "redacted"
  - is_restricted = False (safe for broader distribution)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem, ReviewerStatus

_REDACTION_NOTICE = (
    "[CONTENT REDACTED — Original evidence is access-controlled. "
    "Contact the audit team for access authorisation.]"
)
_REDACTED_MIME = "text/plain"
_EVIDENCE_ROOT = Path("data/evidence")


def redact_evidence(
    db: Session,
    evidence_item_id: str,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> EvidenceItem:
    """Mark original item as restricted and return a new sanitised copy.

    The redacted item's extracted_text is replaced by _REDACTION_NOTICE.
    The redacted file is stored in the same evidence root as the original.
    """
    original = db.get(EvidenceItem, evidence_item_id)
    if original is None:
        raise ValueError(f"EvidenceItem {evidence_item_id!r} not found")

    original.is_restricted = True

    redacted_text = _REDACTION_NOTICE
    if reason:
        redacted_text += f"\nReason: {reason}"
    redacted_bytes = redacted_text.encode("utf-8")
    sha = hashlib.sha256(redacted_bytes).hexdigest()
    redacted_filename = f"REDACTED_{Path(original.source_file).name}"

    dest_dir = _EVIDENCE_ROOT / original.project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sha}.txt"
    if not dest.exists():
        dest.write_bytes(redacted_bytes)

    redacted_item = EvidenceItem(
        project_id=original.project_id,
        evidence_request_id=original.evidence_request_id,
        source_file=redacted_filename,
        sha256=sha,
        mime=_REDACTED_MIME,
        extracted_text=redacted_text,
        classification="redacted",
        reviewer_status=ReviewerStatus.accepted.value,
        is_restricted=False,
    )
    db.add(redacted_item)
    db.flush()
    return redacted_item
