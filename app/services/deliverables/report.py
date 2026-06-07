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
from app.models.delivery import Deliverable, DeliverableKind, RemediationAction
from app.models.evidence import EvidenceItem
from app.models.scan import ScanJob
from app.models.scope import Requirement, ScopeItem
from app.models.tasks import Finding, FindingSeverity, Task
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.deliverables.gap_matrix import _next_version


_SEVERITY_ORDER = {
    FindingSeverity.critical.value: 0,
    FindingSeverity.high.value: 1,
    FindingSeverity.medium.value: 2,
    FindingSeverity.low.value: 3,
    FindingSeverity.info.value: 4,
}

_SEV_COLOUR = {
    "critical": "#991b1b", "high": "#c2410c",
    "medium": "#a16207", "low": "#1d4ed8", "info": "#6b7280",
}
_SEV_BG = {
    "critical": "#fee2e2", "high": "#ffedd5",
    "medium": "#fef9c3", "low": "#dbeafe", "info": "#f3f4f6",
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


def _bar(count: int, max_count: int, colour: str, width: int = 300) -> str:
    px = max(int((count / max(max_count, 1)) * width), 0)
    return (
        f'<div style="display:inline-block;width:{px}px;height:14px;'
        f'background:{colour};vertical-align:middle;border-radius:3px"></div>'
        f'&nbsp;<strong>{count}</strong>'
    )


def _write_html_report(db: Session, project: Project, path: Path) -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    findings = (
        db.query(Finding).filter_by(project_id=project.id).all()
    )
    findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    evidence_items = db.query(EvidenceItem).filter_by(project_id=project.id).all()
    ev_by_id = {ei.id: ei for ei in evidence_items}

    tasks = db.query(Task).filter_by(project_id=project.id).all()
    scan_jobs = (
        db.query(ScanJob).filter_by(project_id=project.id)
        .order_by(ScanJob.created_at.desc()).all()
    )
    remediation_actions = db.query(RemediationAction).filter_by(project_id=project.id).all()
    rem_by_finding: dict = {}
    for ra in remediation_actions:
        rem_by_finding.setdefault(ra.finding_id, []).append(ra)

    scope_items = db.query(ScopeItem).filter_by(project_id=project.id).all()
    requirements = db.query(Requirement).filter_by(project_id=project.id).all()

    # Counts
    sev_counts: dict[str, int] = {s.value: 0 for s in FindingSeverity}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    max_sev = max(sev_counts.values(), default=1) or 1
    task_done = sum(1 for t in tasks if t.status in ("complete", "completed"))
    rem_closed = sum(1 for r in remediation_actions if r.status == "closed")

    # Evidence by classification
    ev_by_class: dict[str, int] = {}
    for ei in evidence_items:
        key = ei.classification or "unclassified"
        ev_by_class[key] = ev_by_class.get(key, 0) + 1

    # ── Section: Executive Summary ──────────────────────────────────────────
    exec_summary = f"""
<table style="width:100%;border-collapse:collapse;margin-bottom:16px">
<thead><tr>
  <th style="background:#1e3a5f;color:#fff;padding:8px 14px;text-align:left">Severity</th>
  <th style="background:#1e3a5f;color:#fff;padding:8px 14px;text-align:left">Count</th>
  <th style="background:#1e3a5f;color:#fff;padding:8px 14px;text-align:left">Distribution</th>
</tr></thead>
<tbody>
"""
    for sev in ["critical", "high", "medium", "low", "info"]:
        cnt = sev_counts.get(sev, 0)
        row_bg = _SEV_BG.get(sev, "#f9f9f9")
        exec_summary += (
            f'<tr style="background:{row_bg}">'
            f'<td style="padding:7px 14px;font-weight:bold;color:{_SEV_COLOUR.get(sev,"#000")}">'
            f'{sev.upper()}</td>'
            f'<td style="padding:7px 14px;font-size:16px;font-weight:bold">{cnt}</td>'
            f'<td style="padding:7px 14px">{_bar(cnt, max_sev, _SEV_COLOUR.get(sev,"#999"))}</td>'
            f'</tr>\n'
        )
    exec_summary += "</tbody></table>"

    # KPI strip
    kpi = f"""
<table style="width:100%;border-collapse:collapse;margin-bottom:20px;text-align:center">
<tr>
  <td style="padding:14px;background:#1e3a5f;color:#fff;border-radius:6px 0 0 6px">
    <div style="font-size:26px;font-weight:bold">{len(findings)}</div>
    <div style="font-size:11px;opacity:.8">Total Findings</div>
  </td>
  <td style="padding:14px;background:#991b1b;color:#fff">
    <div style="font-size:26px;font-weight:bold">{sev_counts.get('critical',0)}</div>
    <div style="font-size:11px;opacity:.8">Critical</div>
  </td>
  <td style="padding:14px;background:#c2410c;color:#fff">
    <div style="font-size:26px;font-weight:bold">{sev_counts.get('high',0)}</div>
    <div style="font-size:11px;opacity:.8">High</div>
  </td>
  <td style="padding:14px;background:#a16207;color:#fff">
    <div style="font-size:26px;font-weight:bold">{sev_counts.get('medium',0)}</div>
    <div style="font-size:11px;opacity:.8">Medium</div>
  </td>
  <td style="padding:14px;background:#1d4ed8;color:#fff">
    <div style="font-size:26px;font-weight:bold">{sev_counts.get('low',0)}</div>
    <div style="font-size:11px;opacity:.8">Low</div>
  </td>
  <td style="padding:14px;background:#4b5563;color:#fff">
    <div style="font-size:26px;font-weight:bold">{sev_counts.get('info',0)}</div>
    <div style="font-size:11px;opacity:.8">Info</div>
  </td>
  <td style="padding:14px;background:#064e3b;color:#fff">
    <div style="font-size:26px;font-weight:bold">{task_done}/{len(tasks)}</div>
    <div style="font-size:11px;opacity:.8">Tasks Done</div>
  </td>
  <td style="padding:14px;background:#065f46;color:#fff;border-radius:0 6px 6px 0">
    <div style="font-size:26px;font-weight:bold">{rem_closed}/{len(remediation_actions)}</div>
    <div style="font-size:11px;opacity:.8">Remediations</div>
  </td>
</tr>
</table>"""

    # ── Section: Risk Matrix (text-based) ──────────────────────────────────
    _rm_cell = {
        (4, 4): ("critical", sev_counts.get("critical", 0)),
        (3, 3): ("high", sev_counts.get("high", 0)),
        (2, 2): ("medium", sev_counts.get("medium", 0)),
        (1, 1): ("low", sev_counts.get("low", 0)),
        (0, 0): ("info", sev_counts.get("info", 0)),
    }
    _rm_bg = [
        ["#bbf7d0","#bbf7d0","#fef08a","#fed7aa","#fca5a5"],
        ["#bbf7d0","#fef08a","#fef08a","#fca5a5","#fca5a5"],
        ["#bbf7d0","#fef08a","#fca5a5","#fca5a5","#f87171"],
        ["#fef08a","#fed7aa","#f87171","#f87171","#ef4444"],
        ["#fed7aa","#f87171","#ef4444","#dc2626","#991b1b"],
    ]
    lik_labels = ["Low", "Medium", "High", "V.High", "Critical"]
    risk_matrix_html = """
<table style="border-collapse:collapse;margin-bottom:6px">
<thead><tr><th style="padding:6px 12px;background:#334155;color:#fff;font-size:11px">L / I</th>"""
    for imp in lik_labels:
        risk_matrix_html += f'<th style="padding:6px 14px;background:#334155;color:#fff;font-size:11px">{imp}</th>'
    risk_matrix_html += "</tr></thead><tbody>"
    for row in range(4, -1, -1):
        risk_matrix_html += f'<tr><td style="padding:6px 12px;background:#334155;color:#fff;font-size:11px;font-weight:bold">{lik_labels[row]}</td>'
        for col in range(5):
            bg = _rm_bg[row][col]
            cell = _rm_cell.get((row, col))
            if cell and cell[1] > 0:
                inner = (
                    f'<span style="display:inline-block;width:28px;height:28px;border-radius:50%;'
                    f'background:{_SEV_COLOUR.get(cell[0],"#666")};color:#fff;'
                    f'font-weight:bold;font-size:13px;line-height:28px;text-align:center">'
                    f'{cell[1]}</span>'
                )
            else:
                inner = ""
            risk_matrix_html += f'<td style="padding:8px 14px;background:{bg};text-align:center;width:70px">{inner}</td>'
        risk_matrix_html += "</tr>"
    risk_matrix_html += "</tbody></table>"
    risk_matrix_html += '<p style="font-size:11px;color:#666">Axes: Likelihood (rows) × Impact (cols). Bubbles = finding count at that severity.</p>'

    # ── Section: Findings Detail ────────────────────────────────────────────
    findings_html = ""
    for f in findings:
        colour = _SEV_COLOUR.get(f.severity, "#666")
        bg = _SEV_BG.get(f.severity, "#f9f9f9")
        ev_refs = ""
        if f.evidence_item_ids:
            for eid in f.evidence_item_ids:
                ei = ev_by_id.get(eid)
                label = (ei.source_file if ei else eid) or eid
                ev_refs += f"<li style='font-size:12px'>{label}</li>"
        ev_section = f"<ul style='margin:4px 0 0'>{ev_refs}</ul>" if ev_refs else "<em style='color:#999'>No evidence linked.</em>"

        actions = rem_by_finding.get(f.id, [])
        rem_html = ""
        if actions:
            closed = sum(1 for a in actions if a.status == "closed")
            rem_html = f"<p style='font-size:12px'><strong>Remediation:</strong> {closed}/{len(actions)} actions closed</p>"

        retest_html = ""
        if f.retest_status:
            retest_html = f"<p style='font-size:12px'><strong>Retest:</strong> {f.retest_status}</p>"

        phase_html = ""
        if f.phase_tag:
            phase_html = f"<span style='background:#e2e8f0;padding:2px 6px;border-radius:3px;font-size:11px'>{f.phase_tag}</span>&nbsp;"

        findings_html += f"""
<div style="border:1px solid #e5e7eb;padding:14px 16px;margin-bottom:14px;border-left:6px solid {colour};background:{bg};border-radius:4px">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
    <span style="background:{colour};color:#fff;padding:3px 10px;border-radius:3px;font-size:12px;font-weight:bold">{f.severity.upper()}</span>
    {phase_html}
    <h3 style="margin:0;font-size:14px;color:#1e293b">{f.title}</h3>
  </div>
  <p style="font-size:12px;margin:4px 0"><strong>Status:</strong> {f.status} &nbsp;|&nbsp; <strong>Source:</strong> {f.source}</p>
  <p style="font-size:13px;margin:6px 0;color:#374151">{f.description or '<em style="color:#999">No description recorded.</em>'}</p>
  {retest_html}{rem_html}
  <p style="font-size:12px;margin:6px 0 2px"><strong>Evidence:</strong></p>
  {ev_section}
</div>"""

    # ── Section: Scan Jobs ──────────────────────────────────────────────────
    scan_html = ""
    if scan_jobs:
        scan_html = """<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Host</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Phases</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Tier</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Status</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Started</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Finished</th>
  <th style="background:#1e3a5f;color:#fff;padding:7px 12px;text-align:left;font-size:12px">Imported</th>
</tr></thead><tbody>"""
        for i, job in enumerate(scan_jobs):
            row_bg = "#f8fafc" if i % 2 == 0 else "#fff"
            phases_str = ", ".join(job.phases or []) or "—"
            started = job.started_at.strftime("%Y-%m-%d %H:%M") if job.started_at else "—"
            finished = job.finished_at.strftime("%Y-%m-%d %H:%M") if job.finished_at else "—"
            ir = job.import_result or {}
            imported = str(ir.get("findings_imported", ir.get("created", "—")))
            scan_html += (
                f'<tr style="background:{row_bg}">'
                f'<td style="padding:7px 12px;font-size:12px;font-weight:bold">{job.host}</td>'
                f'<td style="padding:7px 12px;font-size:12px">{phases_str}</td>'
                f'<td style="padding:7px 12px;font-size:12px">{job.tier or "standard"}</td>'
                f'<td style="padding:7px 12px;font-size:12px;font-weight:bold;color:'
                f'{"#15803d" if job.status=="completed" else "#b91c1c" if job.status=="failed" else "#92400e"}">'
                f'{job.status}</td>'
                f'<td style="padding:7px 12px;font-size:12px">{started}</td>'
                f'<td style="padding:7px 12px;font-size:12px">{finished}</td>'
                f'<td style="padding:7px 12px;font-size:12px">{imported}</td>'
                f'</tr>\n'
            )
        scan_html += "</tbody></table>"
    else:
        scan_html = "<p><em>No PT-Orc scans recorded.</em></p>"

    # ── Section: Evidence ───────────────────────────────────────────────────
    ev_html = ""
    if evidence_items:
        ev_html = """<table style="width:100%;border-collapse:collapse">
<thead><tr>
  <th style="background:#1e3a5f;color:#fff;padding:6px 12px;font-size:12px;text-align:left">File</th>
  <th style="background:#1e3a5f;color:#fff;padding:6px 12px;font-size:12px;text-align:left">Classification</th>
  <th style="background:#1e3a5f;color:#fff;padding:6px 12px;font-size:12px;text-align:left">SHA256</th>
</tr></thead><tbody>"""
        for i, ei in enumerate(evidence_items):
            row_bg = "#f8fafc" if i % 2 == 0 else "#fff"
            ev_html += (
                f'<tr style="background:{row_bg}">'
                f'<td style="padding:6px 12px;font-size:12px">{ei.source_file or "—"}</td>'
                f'<td style="padding:6px 12px;font-size:12px">{ei.classification or "unclassified"}</td>'
                f'<td style="padding:6px 12px;font-size:12px;font-family:monospace">'
                f'{ei.sha256[:16] if ei.sha256 else "—"}…</td>'
                f'</tr>\n'
            )
        ev_html += "</tbody></table>"
    else:
        ev_html = "<p><em>No evidence items recorded.</em></p>"

    # ── Section: Scope ──────────────────────────────────────────────────────
    scope_html = ""
    if scope_items:
        scope_html = "<ul>"
        for si in scope_items:
            approved_str = "✓ approved" if si.approved else "pending"
            scope_html += f"<li style='font-size:13px;margin-bottom:4px'><strong>[{si.kind}]</strong> <code>{si.value}</code> — {approved_str}</li>"
        scope_html += "</ul>"
    else:
        scope_html = "<p><em>No scope items defined.</em></p>"

    # ── Assemble full document ──────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>VAPT Report — {project.id[:8]}</title>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;margin:0;padding:0;color:#1e293b}}
  .page{{max-width:1100px;margin:0 auto;padding:32px 40px}}
  h1{{color:#1e3a5f;font-size:24px;margin:0 0 6px}}
  h2{{color:#1e3a5f;font-size:17px;margin:28px 0 10px;padding-bottom:6px;border-bottom:2px solid #e2e8f0}}
  h3{{color:#334155;font-size:14px;margin:20px 0 8px}}
  .draft-banner{{background:#fef3c7;border:1px solid #fcd34d;padding:10px 16px;border-radius:6px;margin-bottom:24px;font-size:13px;color:#92400e}}
  .meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px}}
  .meta-item{{background:#f8fafc;border:1px solid #e2e8f0;padding:10px 14px;border-radius:6px}}
  .meta-item label{{font-size:11px;color:#64748b;display:block;margin-bottom:2px}}
  .meta-item span{{font-weight:600;color:#1e293b}}
  code{{background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:12px}}
  hr{{border:none;border-top:1px solid #e2e8f0;margin:24px 0}}
  @media print{{.page{{padding:16px 24px}} h2{{page-break-before:always}} h2:first-of-type{{page-break-before:avoid}}}}
</style>
</head>
<body><div class="page">

<h1>VAPT Assessment Report</h1>
<p style="color:#64748b;font-size:13px">TechGuard Labs Confidential &nbsp;|&nbsp; Generated: {now_str}</p>

<div class="draft-banner">
  ⚠ DRAFT — This report has not been formally released. Gate G6 approval required before distribution.
</div>

<div class="meta-grid">
  <div class="meta-item"><label>Project ID</label><span>{project.id}</span></div>
  <div class="meta-item"><label>Service Type</label><span>{project.service_type.upper() if project.service_type else "—"}</span></div>
  <div class="meta-item"><label>Project Status</label><span>{project.status}</span></div>
  <div class="meta-item"><label>Scope Items</label><span>{len(scope_items)}</span></div>
  <div class="meta-item"><label>Requirements</label><span>{len(requirements)}</span></div>
  <div class="meta-item"><label>Pack</label><span>{project.pack_id or "—"}</span></div>
</div>

<h2>1. Executive Summary</h2>
<p>This report presents the results of the VAPT (Vulnerability Assessment and Penetration Test) engagement.
All findings have been assessed against CVSS-aligned severity definitions and are presented in priority order.</p>
{kpi}
{exec_summary}

<h2>2. Risk Matrix</h2>
<p>Findings are plotted by likelihood and impact to support risk-based prioritisation.</p>
{risk_matrix_html}

<h2>3. Findings Detail</h2>
{findings_html or '<p>No findings recorded for this engagement.</p>'}

<h2>4. PT-Orc Scan Outputs</h2>
{scan_html}

<h2>5. Evidence Inventory</h2>
{ev_html}

<h2>6. Scope</h2>
{scope_html}

<hr>
<p style="font-size:11px;color:#94a3b8;text-align:center">
  TechGuard Labs &nbsp;|&nbsp; CONFIDENTIAL &nbsp;|&nbsp; This document is intended solely for the named client.
  Unauthorised disclosure is prohibited. &nbsp;|&nbsp; {now_str}
</p>
</div></body></html>"""
    path.write_text(html, encoding="utf-8")
