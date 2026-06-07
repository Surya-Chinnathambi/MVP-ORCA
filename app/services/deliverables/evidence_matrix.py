"""Evidence matrix deliverable — evidence-to-requirement mapping (XLSX + HTML)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.evidence import EvidenceItem, EvidenceRequest
from app.models.scope import Requirement
from app.services.deliverables.gap_matrix import _next_version


def generate_evidence_matrix(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.evidence_matrix)
    html_path = output_dir / f"evidence_matrix_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.evidence_matrix,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    db.flush()
    return deliverable


def _write_html(db: Session, project: Project, path: Path) -> None:
    requirements = db.query(Requirement).filter_by(project_id=project.id).all()
    evidence_items = db.query(EvidenceItem).filter_by(project_id=project.id).all()
    evidence_requests = db.query(EvidenceRequest).filter_by(project_id=project.id).all()

    req_rows = ""
    for req in requirements:
        # Evidence requests linked to this requirement
        linked_ers = [er for er in evidence_requests if er.requirement_id == req.id]
        er_titles = ", ".join(er.title for er in linked_ers) if linked_ers else "—"
        req_rows += (
            f"<tr><td>{req.ref_code}</td><td>{req.category}</td>"
            f"<td class='truncate max-w-xs'>{req.text[:80]}…</td>"
            f"<td>{er_titles}</td></tr>\n"
        )

    ev_rows = ""
    for item in evidence_items:
        ev_rows += (
            f"<tr><td class='font-mono text-xs'>{item.id[:8]}…</td>"
            f"<td>{item.source_file}</td>"
            f"<td>{item.classification or '—'}</td>"
            f"<td>{item.reviewer_status}</td>"
            f"<td>{item.internal_lifecycle_state}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Evidence Matrix</title>
<style>
  body {{ font-family: sans-serif; margin: 2rem; font-size: 13px; }}
  h1 {{ font-size: 1.2rem; margin-bottom: 1rem; }}
  h2 {{ font-size: 1rem; margin: 1.5rem 0 0.5rem; color: #374151; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
  th {{ background: #f3f4f6; text-align: left; padding: 6px 10px; font-size: 11px; text-transform: uppercase; }}
  td {{ padding: 6px 10px; border-top: 1px solid #e5e7eb; }}
  .truncate {{ max-width: 300px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}
</style>
</head>
<body>
<h1>Evidence Matrix — Project {project.id[:8]}</h1>
<p style="color:#6b7280; font-size:12px">Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>

<h2>Requirements ({len(requirements)})</h2>
<table>
<tr><th>Ref Code</th><th>Category</th><th>Requirement</th><th>Evidence Requests</th></tr>
{req_rows or '<tr><td colspan="4" style="color:#9ca3af">No requirements generated yet.</td></tr>'}
</table>

<h2>Evidence Items ({len(evidence_items)})</h2>
<table>
<tr><th>ID</th><th>Source File</th><th>Classification</th><th>Reviewer Status</th><th>Lifecycle State</th></tr>
{ev_rows or '<tr><td colspan="5" style="color:#9ca3af">No evidence items uploaded yet.</td></tr>'}
</table>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
