"""Concrete job implementations executed by RQ workers.

Each function opens its own DB session, does the work, commits, and closes.
Results are identical to the synchronous MVP paths — only execution is async.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.db import SessionLocal
from app.models.evidence import EvidenceItem

logger = logging.getLogger(__name__)


# ── Evidence extraction ───────────────────────────────────────────────────────

def run_evidence_extraction(evidence_item_id: str) -> dict:
    """Extract text from an already-ingested EvidenceItem and persist it.

    Returns a dict with id, sha256, extracted_text (first 200 chars), classification.
    """
    from app.services.evidence.ingest import extract_text, storage_path as _storage_path
    from app.services.evidence.keyword_classify import classify_text

    db = SessionLocal()
    try:
        item = db.get(EvidenceItem, evidence_item_id)
        if item is None:
            raise ValueError(f"EvidenceItem {evidence_item_id!r} not found")

        stored = _storage_path(item.project_id, item.sha256, Path(item.source_file).name)
        if stored.exists():
            text = extract_text(stored, item.mime or "application/octet-stream")
            category = classify_text(text, mime=item.mime, filename=stored.name)
        else:
            text = item.extracted_text or ""
            category = item.classification or "uncategorized"

        if text and item.extracted_text != text:
            item.extracted_text = text
        if category and item.classification != category:
            item.classification = category

        db.commit()
        return {
            "id": item.id,
            "sha256": item.sha256,
            "extracted_text_preview": (text or "")[:200],
            "classification": category,
        }
    finally:
        db.close()


# ── PT-Orc import ─────────────────────────────────────────────────────────────

def run_ptorc_import(project_id: str, run_dir: str) -> dict:
    """Import a PT-Orc run directory. Returns counts of imported items."""
    from ptorc_adapter.importer import run_import

    db = SessionLocal()
    try:
        result = run_import(db, project_id, Path(run_dir))
        return {
            "project_id": result.project_id,
            "scope_items": len(result.scope_items),
            "evidence_items": len(result.evidence_items),
            "findings": len(result.findings),
        }
    finally:
        db.close()


# ── Deliverable generation ────────────────────────────────────────────────────

def run_gap_matrix(project_id: str, output_dir: str) -> dict:
    from app.models.clients import Project
    from app.services.deliverables.gap_matrix import generate_gap_matrix

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id!r} not found")
        xlsx_del, html_del = generate_gap_matrix(db, project, Path(output_dir))
        db.commit()
        return {"xlsx": xlsx_del.file_path, "html": html_del.file_path}
    finally:
        db.close()


def run_roadmap(project_id: str, output_dir: str) -> dict:
    from app.models.clients import Project
    from app.services.deliverables.roadmap import generate_roadmap

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id!r} not found")
        md_del, html_del = generate_roadmap(db, project, Path(output_dir))
        db.commit()
        return {"md": md_del.file_path, "html": html_del.file_path}
    finally:
        db.close()


def run_report(project_id: str, output_dir: str) -> dict:
    from app.models.clients import Project
    from app.services.deliverables.report import generate_report

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id!r} not found")
        report_del = generate_report(db, project, Path(output_dir))
        db.commit()
        return {"html": report_del.file_path}
    finally:
        db.close()
