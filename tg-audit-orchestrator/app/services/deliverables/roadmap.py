"""Roadmap deliverable — remediation actions grouped by priority/severity.

Exports to Markdown and HTML. Creates/versions a Deliverable record.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind, RemediationAction
from app.models.tasks import Finding, FindingSeverity
from app.services.deliverables.gap_matrix import _next_version


_SEVERITY_ORDER = {
    FindingSeverity.critical.value: 0,
    FindingSeverity.high.value: 1,
    FindingSeverity.medium.value: 2,
    FindingSeverity.low.value: 3,
    FindingSeverity.info.value: 4,
}


def _build_roadmap_items(db: Session, project_id: str) -> list[dict]:
    """Return remediation actions enriched with finding severity, sorted by priority."""
    actions = (
        db.query(RemediationAction)
        .filter_by(project_id=project_id)
        .all()
    )
    rows = []
    for action in actions:
        finding = db.get(Finding, action.finding_id)
        severity = finding.severity if finding else "info"
        rows.append({
            "action_id": action.id,
            "finding_title": finding.title if finding else "Unknown",
            "severity": severity,
            "action": action.action,
            "status": action.status,
            "owner_id": action.owner_id or "—",
            "target_date": str(action.target_date) if action.target_date else "—",
            "residual_risk": action.residual_risk or "—",
        })

    rows.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 99))
    return rows


def generate_roadmap(
    db: Session,
    project: Project,
    output_dir: Path,
    actor_id: Optional[str] = None,
) -> tuple[Deliverable, Deliverable]:
    """Generate Markdown + HTML roadmap. Returns (md_deliverable, html_deliverable)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    items = _build_roadmap_items(db, project.id)
    now = datetime.now(timezone.utc)

    version = _next_version(db, project.id, DeliverableKind.roadmap)
    md_path = output_dir / f"roadmap_v{version}.md"
    html_path = output_dir / f"roadmap_v{version}.html"

    _write_md(items, md_path, project)
    _write_html_roadmap(items, html_path, project)

    md_del = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.roadmap,
        format="md",
        file_path=str(md_path),
        generated_at=now,
        version=version,
    )
    html_del = Deliverable(
        id=str(uuid.uuid4()),
        project_id=project.id,
        kind=DeliverableKind.roadmap,
        format="html",
        file_path=str(html_path),
        generated_at=now,
        version=version,
    )
    db.add(md_del)
    db.add(html_del)
    return md_del, html_del


def _write_md(items: list[dict], path: Path, project: Project) -> None:
    lines = [
        f"# Remediation Roadmap",
        f"",
        f"**Project:** {project.id}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
    ]
    current_sev = None
    for item in items:
        if item["severity"] != current_sev:
            current_sev = item["severity"]
            lines.append(f"## {current_sev.upper()}")
            lines.append("")

        lines.append(f"### {item['finding_title']}")
        lines.append(f"")
        lines.append(f"- **Action:** {item['action']}")
        lines.append(f"- **Status:** {item['status']}")
        lines.append(f"- **Owner:** {item['owner_id']}")
        lines.append(f"- **Target date:** {item['target_date']}")
        lines.append(f"- **Residual risk:** {item['residual_risk']}")
        lines.append(f"")

    if not items:
        lines.append("*No remediation actions recorded.*")

    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html_roadmap(items: list[dict], path: Path, project: Project) -> None:
    _SEV_COLOURS = {
        "critical": "#c00000", "high": "#ff0000",
        "medium": "#ff9900", "low": "#ffff00", "info": "#cccccc",
    }

    rows_html = ""
    for item in items:
        colour = _SEV_COLOURS.get(item["severity"], "#eee")
        rows_html += (
            f'<tr>'
            f'<td style="background:{colour};color:{"#fff" if item["severity"] in ("critical","high") else "#000"}">'
            f'{item["severity"]}</td>'
            f'<td>{item["finding_title"]}</td>'
            f'<td>{item["action"]}</td>'
            f'<td>{item["status"]}</td>'
            f'<td>{item["owner_id"]}</td>'
            f'<td>{item["target_date"]}</td>'
            f'<td>{item["residual_risk"]}</td>'
            f'</tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Remediation Roadmap — {project.id}</title>
<style>
body{{font-family:Arial,sans-serif;font-size:13px;margin:20px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left}}
th{{background:#1f4e79;color:#fff}}
tr:nth-child(even){{background:#f5f5f5}}
</style></head>
<body>
<h2>Remediation Roadmap</h2>
<p>Project: {project.id} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
<table>
<thead><tr>
<th>Severity</th><th>Finding</th><th>Action</th><th>Status</th>
<th>Owner</th><th>Target Date</th><th>Residual Risk</th>
</tr></thead>
<tbody>{rows_html or '<tr><td colspan="7">No remediation actions recorded.</td></tr>'}</tbody>
</table>
</body></html>"""
    path.write_text(html, encoding="utf-8")
