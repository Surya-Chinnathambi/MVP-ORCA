"""Evidence manifest — emit evidence_manifest.jsonl per project."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.evidence import EvidenceItem

_EVIDENCE_ROOT = Path("data/evidence")


def manifest_path(project_id: str) -> Path:
    d = _EVIDENCE_ROOT / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "manifest.jsonl"


def _item_to_record(item: EvidenceItem) -> dict:
    linked_refs = []
    if item.evidence_request_id:
        linked_refs.append({"type": "evidence_request", "id": item.evidence_request_id})
    return {
        "id": item.id,
        "sha256": item.sha256,
        "source_file": item.source_file,
        "mime": item.mime,
        "classification": item.classification or "general",
        "linked_refs": linked_refs,
        "reviewer_status": item.reviewer_status,
    }


def append_item(project_id: str, item: EvidenceItem) -> None:
    """Append a single item line to the project manifest."""
    path = manifest_path(project_id)
    record = _item_to_record(item)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_manifest(db: Session, project_id: str) -> Path:
    """Rebuild manifest from all project EvidenceItems; return path."""
    items = db.query(EvidenceItem).filter_by(project_id=project_id).all()
    path = manifest_path(project_id)
    with open(path, "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(_item_to_record(item), ensure_ascii=False) + "\n")
    return path
