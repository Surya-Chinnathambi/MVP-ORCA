"""Client action plan deliverable — remediation actions grouped by finding."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind, RemediationAction
from app.models.tasks import Finding
from app.services.deliverables.gap_matrix import _next_version


def generate_client_action_plan(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> Deliverable:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(db, project.id, DeliverableKind.client_action_plan)
    html_path = output_dir / f"client_action_plan_v{version}.html"
    _write_html(db, project, html_path)

    deliverable = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.client_action_plan,
        format="html",
        file_path=str(html_path),
        generated_at=datetime.now(timezone.utc),
        version=version,
    )
    db.add(deliverable)
    return deliverable


def _write_html(db: Session, project: Project, path: Path) -> None:
    findings = db.query(Finding).filter_by(project_id=project.id).all()
    findings_by_id = {f.id: f for f in findings}
    actions = (
        db.query(RemediationAction)
        .filter_by(project_id=project.id)
        .all()
    )
    actions_by_finding: dict[str, list] = {}
    for a in actions:
        actions_by_finding.setdefault(a.finding_id, []).append(a)

    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 99)
    )

    sections = ""
    for f in sorted_findings:
        f_actions = actions_by_finding.get(f.id, [])
        action_rows = ""
        for a in f_actions:
            due = a.target_date.strftime("%Y-%m-%d") if a.target_date else "TBD"
            action_rows += (
                f"<tr><td>{a.action}</td><td>{a.status}</td><td>{due}</td>"
                f"<td>{a.residual_risk or ''}</td></tr>"
            )
        sections += f"""
<div style='border:1px solid #ccc;padding:14px;margin-bottom:16px'>
  <h3>[{f.severity.upper()}] {f.title}</h3>
  <p><strong>Status:</strong> {f.status}</p>
  {'<table style="width:100%;border-collapse:collapse"><thead><tr><th style="border:1px solid #ccc;padding:6px">Action</th><th style="border:1px solid #ccc;padding:6px">Status</th><th style="border:1px solid #ccc;padding:6px">Due</th><th style="border:1px solid #ccc;padding:6px">Residual Risk</th></tr></thead><tbody>' + action_rows + '</tbody></table>' if action_rows else '<p><em>No remediation actions recorded.</em></p>'}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Client Action Plan — {project.id}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px;max-width:1000px}}h3{{color:#1f4e79}}</style></head>
<body>
<h1>Client Action Plan</h1>
<p><strong>Project:</strong> {project.id} | <strong>Generated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<p><em>DRAFT — not released</em></p>
{sections or '<p>No findings recorded.</p>'}
</body></html>"""
    path.write_text(html, encoding="utf-8")
