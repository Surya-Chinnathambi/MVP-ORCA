"""Report deliverable — HTML executive summary + findings + evidence references.

Gate 6: a report can only be marked *released* after an approved ApprovalRequest.
The release endpoint in the API router enforces this via request_approval.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.evidence import EvidenceItem
from app.models.tasks import Finding, FindingSeverity
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.deliverables.gap_matrix import _next_version


_SEVERITY_ORDER = {
    FindingSeverity.critical.value: 0,
    FindingSeverity.high.value: 1,
    FindingSeverity.medium.value: 2,
    FindingSeverity.low.value: 3,
    FindingSeverity.info.value: 4,
}


def generate_report(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    """Generate draft HTML report. Does NOT mark it released."""
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.report)
    html_path = output_dir / f"report_v{version}.html"
    _write_html_report(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.report,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def has_release_approval(db: Session, deliverable_id: str) -> bool:
    """Return True if there is an approved ApprovalRequest for this deliverable's release."""
    approval = (
        db.query(ApprovalRequest)
        .filter_by(
            target_type="deliverable",
            target_id=deliverable_id,
            status=ApprovalStatus.approved,
        )
        .first()
    )
    return approval is not None


def _write_html_report(db: Session, project: Project, path: Path) -> None:
    findings = (
        db.query(Finding)
        .filter_by(project_id=project.id)
        .all()
    )
    findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    evidence_items = (
        db.query(EvidenceItem)
        .filter_by(project_id=project.id)
        .all()
    )
    ev_by_id = {ei.id: ei for ei in evidence_items}

    _SEV_COLOURS = {
        "critical": "#c00000", "high": "#ff0000",
        "medium": "#ff9900", "low": "#ffff00", "info": "#cccccc",
    }

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    summary_rows = "".join(
        f'<tr><td>{sev}</td><td>{counts.get(sev, 0)}</td></tr>'
        for sev in ["critical", "high", "medium", "low", "info"]
    )

    findings_html = ""
    for f in findings:
        colour = _SEV_COLOURS.get(f.severity, "#eee")
        ev_refs = ""
        if f.evidence_item_ids:
            for eid in f.evidence_item_ids:
                ei = ev_by_id.get(eid)
                label = ei.source_file if ei else eid
                ev_refs += f'<li>{label}</li>'
        ev_section = f'<ul>{ev_refs}</ul>' if ev_refs else '<em>No evidence linked.</em>'

        findings_html += f"""
<div style="border:1px solid #ccc;padding:12px;margin-bottom:14px;border-left:6px solid {colour}">
  <h3 style="margin:0 0 6px">[{f.severity.upper()}] {f.title}</h3>
  <p><strong>Status:</strong> {f.status} | <strong>Source:</strong> {f.source}</p>
  <p>{f.description or '<em>No description.</em>'}</p>
  <p><strong>Evidence:</strong></p>
  {ev_section}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Audit Report — {project.id}</title>
<style>
body{{font-family:Arial,sans-serif;font-size:13px;margin:20px;max-width:1000px}}
table{{border-collapse:collapse}}
th,td{{border:1px solid #ccc;padding:6px 12px}}
th{{background:#1f4e79;color:#fff}}
h2{{color:#1f4e79}}
</style></head>
<body>
<h1>Audit Report</h1>
<p><strong>Project:</strong> {project.id}</p>
<p><strong>Service type:</strong> {project.service_type}</p>
<p><strong>Status:</strong> {project.status}</p>
<p><strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><em>DRAFT — not released</em></p>
<hr>

<h2>Executive Summary</h2>
<p>This report summarises the findings and evidence gathered during the audit engagement.</p>

<h3>Finding Counts by Severity</h3>
<table>
<thead><tr><th>Severity</th><th>Count</th></tr></thead>
<tbody>{summary_rows}</tbody>
</table>

<hr>
<h2>Findings</h2>
{findings_html or '<p>No findings recorded.</p>'}

<hr>
<h2>Evidence References</h2>
<ul>
{''.join(f'<li>{ei.source_file} ({ei.classification or "unclassified"}) — {ei.sha256[:12]}…</li>' for ei in evidence_items)
or '<li>No evidence items.</li>'}
</ul>

</body></html>"""
    path.write_text(html, encoding="utf-8")
