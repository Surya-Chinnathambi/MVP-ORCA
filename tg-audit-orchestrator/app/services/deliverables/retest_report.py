"""Retest report deliverable — summarises retest results vs original findings."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.tasks import Finding, FindingStatus
from app.services.deliverables.gap_matrix import _next_version


def generate_retest_report(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.retest_report)
    html_path = output_dir / f"retest_report_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.retest_report,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def _write_html(db: Session, project: Project, path: Path) -> None:
    findings = db.query(Finding).filter_by(project_id=project.id).all()
    ptorc_findings = [f for f in findings if f.source == "ptorc"]

    _STATUS_LABEL = {
        "passed": ("PASSED", "#008000"),
        "failed": ("FAILED", "#c00000"),
        "partial": ("PARTIAL", "#ff9900"),
        "pending": ("PENDING", "#888888"),
        "in_progress": ("IN PROGRESS", "#0070c0"),
        "n/a": ("N/A", "#cccccc"),
    }

    rows = ""
    for f in ptorc_findings:
        rs = f.retest_status or "n/a"
        label, colour = _STATUS_LABEL.get(rs, (rs.upper(), "#cccccc"))
        rows += (
            f"<tr>"
            f"<td>{f.title}</td>"
            f"<td>{f.severity.upper()}</td>"
            f"<td style='color:{colour};font-weight:bold'>{label}</td>"
            f"<td>{f.phase_tag or ''}</td>"
            f"<td>{f.ptorc_run_id or ''}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Retest Report — {project.id}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;max-width:1000px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:6px 10px}}
th{{background:#1f4e79;color:#fff}}</style></head>
<body>
<h1>Retest Report</h1>
<p><strong>Project:</strong> {project.id} | <strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><em>DRAFT — not released</em></p>
<h2>Retest Results</h2>
<table>
<thead><tr><th>Finding</th><th>Severity</th><th>Retest Status</th><th>Phase</th><th>Run ID</th></tr></thead>
<tbody>{rows or '<tr><td colspan=5>No PT-Orc findings.</td></tr>'}</tbody>
</table>
</body></html>"""
    path.write_text(html, encoding="utf-8")
