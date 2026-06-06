"""Summary deliverable — concise HTML overview of the engagement status.

Intended as a quick-read one-pager: scope, evidence status, finding counts by severity.
Not gated (no Gate 6 required) — can be generated at any point.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingSeverity
from app.services.deliverables.gap_matrix import _next_version


def generate_summary(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.summary)
    html_path = output_dir / f"summary_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.summary,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def _write_html(db: Session, project: Project, path: Path) -> None:
    scope_items = db.query(ScopeItem).filter_by(project_id=project.id).all()
    approved_scope = [si for si in scope_items if si.approved]

    evidence_reqs = db.query(EvidenceRequest).filter_by(project_id=project.id).all()
    received = sum(1 for er in evidence_reqs if er.status == EvidenceRequestStatus.received.value)
    total_er = len(evidence_reqs)

    findings = db.query(Finding).filter_by(project_id=project.id).all()
    severity_counts = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    scope_rows = "".join(
        f"<tr><td>{si.kind}</td><td>{si.value}</td><td>{'✓' if si.approved else '—'}</td></tr>"
        for si in scope_items
    )
    finding_rows = "".join(
        f"<tr><td>{sev.upper()}</td><td>{severity_counts.get(sev, 0)}</td></tr>"
        for sev in ["critical", "high", "medium", "low", "info"]
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Engagement Summary — {project.id}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;max-width:900px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:6px 10px}}
th{{background:#1f4e79;color:#fff}}h2{{color:#1f4e79}}
.stat{{display:inline-block;margin:10px;padding:12px 20px;background:#f0f0f0;
border-radius:4px;text-align:center;min-width:100px}}</style></head>
<body>
<h1>Engagement Summary</h1>
<p><strong>Project:</strong> {project.id} &nbsp;|&nbsp;
   <strong>Status:</strong> {project.status} &nbsp;|&nbsp;
   <strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<div>
  <div class='stat'><div style='font-size:2em'>{len(approved_scope)}/{len(scope_items)}</div>Scope items approved</div>
  <div class='stat'><div style='font-size:2em'>{received}/{total_er}</div>Evidence received</div>
  <div class='stat'><div style='font-size:2em'>{len(findings)}</div>Total findings</div>
</div>
<h2>Scope Items</h2>
<table><thead><tr><th>Kind</th><th>Value</th><th>Approved</th></tr></thead>
<tbody>{scope_rows or '<tr><td colspan=3>No scope items.</td></tr>'}</tbody></table>
<h2>Findings by Severity</h2>
<table><thead><tr><th>Severity</th><th>Count</th></tr></thead>
<tbody>{finding_rows}</tbody></table>
</body></html>"""
    path.write_text(html, encoding="utf-8")
