"""Advisory clinic deck deliverable — agenda + findings linked to advisory clinics."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import AdvisoryClinic, Deliverable, DeliverableKind
from app.models.tasks import Finding
from app.services.deliverables.gap_matrix import _next_version


def generate_advisory_clinic_deck(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.advisory_clinic_deck)
    html_path = output_dir / f"advisory_clinic_deck_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.advisory_clinic_deck,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def _write_html(db: Session, project: Project, path: Path) -> None:
    clinics = db.query(AdvisoryClinic).filter_by(project_id=project.id).all()
    findings_by_id = {
        f.id: f
        for f in db.query(Finding).filter_by(project_id=project.id).all()
    }

    slides = ""
    for clinic in clinics:
        scheduled = (
            clinic.scheduled_for.strftime("%Y-%m-%d %H:%M")
            if clinic.scheduled_for else "TBD"
        )
        linked = ""
        for fid in (clinic.linked_finding_ids or []):
            f = findings_by_id.get(fid)
            if f:
                linked += f"<li>[{f.severity.upper()}] {f.title}</li>"
        agenda_items = ""
        for item in (clinic.agenda or []):
            agenda_items += f"<li>{item}</li>"

        slides += f"""
<div style='border:1px solid #ccc;padding:16px;margin-bottom:20px;border-left:6px solid #1f4e79'>
  <h2 style='margin:0 0 8px;color:#1f4e79'>{clinic.topic}</h2>
  <p><strong>Scheduled:</strong> {scheduled}</p>
  {'<h4>Agenda</h4><ul>' + agenda_items + '</ul>' if agenda_items else ''}
  {'<h4>Linked Findings</h4><ul>' + linked + '</ul>' if linked else ''}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Advisory Clinic Deck — {project.id}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;max-width:900px}}</style></head>
<body>
<h1>Advisory Clinic Deck</h1>
<p><strong>Project:</strong> {project.id} | <strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><em>DRAFT — not released</em></p>
{slides or '<p>No advisory clinics scheduled.</p>'}
</body></html>"""
    path.write_text(html, encoding="utf-8")
