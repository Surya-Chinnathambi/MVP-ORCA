"""Management summary (board-level) deliverable.

Gate 6: release requires an approved ApprovalRequest — same gate as the main report.
Only high/critical findings surfaced; no technical detail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.tasks import Finding, FindingSeverity
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.deliverables.gap_matrix import _next_version


def generate_management_summary(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.management_summary)
    html_path = output_dir / f"management_summary_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.management_summary,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def has_release_approval(db: Session, deliverable_id: str) -> bool:
    return (
        db.query(ApprovalRequest)
        .filter_by(
            target_type="deliverable",
            target_id=deliverable_id,
            status=ApprovalStatus.approved,
        )
        .first()
    ) is not None


def _write_html(db: Session, project: Project, path: Path) -> None:
    findings = db.query(Finding).filter_by(project_id=project.id).all()
    _BOARD_SEVERITIES = {FindingSeverity.critical.value, FindingSeverity.high.value}
    board_findings = [f for f in findings if f.severity in _BOARD_SEVERITIES]
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    summary_rows = "".join(
        f"<tr><td>{sev}</td><td>{counts.get(sev, 0)}</td></tr>"
        for sev in ["critical", "high", "medium", "low", "info"]
    )
    exec_rows = "".join(
        f"<tr><td>[{f.severity.upper()}] {f.title}</td><td>{f.status}</td></tr>"
        for f in board_findings
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Management Summary — {project.id}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;max-width:900px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:6px 10px}}
th{{background:#1f4e79;color:#fff}}h2{{color:#1f4e79}}</style></head>
<body>
<h1>Management Summary</h1>
<p><strong>Project:</strong> {project.id} | <strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><em>DRAFT — requires Gate 6 approval before release</em></p>
<h2>Key Risk Summary</h2>
<table><thead><tr><th>Severity</th><th>Count</th></tr></thead>
<tbody>{summary_rows}</tbody></table>
<h2>Critical and High Findings Requiring Board Attention</h2>
<table><thead><tr><th>Finding</th><th>Status</th></tr></thead>
<tbody>{exec_rows or '<tr><td colspan=2>No critical/high findings.</td></tr>'}</tbody></table>
</body></html>"""
    path.write_text(html, encoding="utf-8")
