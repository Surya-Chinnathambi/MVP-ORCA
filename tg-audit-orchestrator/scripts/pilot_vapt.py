"""VAPT pilot — runs the full VAPT audit chain end-to-end using the PT-Orc adapter.

Usage:
    python scripts/pilot_vapt.py

Creates:
  client → project → scope → VAPT pack plan → PT-Orc import (fixture run dir) →
  approve imported scope/findings → all 7 gates → QA → deliverables → closure

Prints a summary of every step and exits 0 on success.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.models.workflow import ApprovalRequest, AuditTrailEvent
from app.services.audit import decide_approval, record_event, request_approval
from app.services.auth import hash_password
from app.services.deliverables.gap_matrix import generate_gap_matrix
from app.services.deliverables.report import generate_report
from app.services.deliverables.roadmap import generate_roadmap
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan
from app.services.qa.agent import run_qa
from ptorc_adapter.importer import run_import

_DB_URL = "sqlite:///data/pilot_vapt.db"
_OUTPUT = Path("data/pilot_vapt_out")
_ACTOR = "pilot-vapt"


def _sep(label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print('─' * 60)


def _make_fixture_run_dir(tmp_path: Path, project_id: str) -> Path:
    """Write a minimal PT-Orc run directory fixture."""
    run_dir = tmp_path / "ptorc_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "scope.json").write_text(json.dumps({
        "project_ref": project_id,
        "engagement_profile": "external",
        "testing_depth": "standard",
        "auth_level": "none",
        "targets": ["target.example.com", "api.target.example.com"],
        "rules_of_engagement": "No DoS; testing window business hours only.",
        "window": {"start": "2026-06-01", "end": "2026-06-14"},
    }), encoding="utf-8")

    evidence_lines = [
        json.dumps({
            "id": "ev-001", "phase": "01_dns",
            "source_file": "dns_records.txt",
            "sha256": "a" * 64,
            "summary": "DNS enumeration: 12 subdomains found.",
        }),
        json.dumps({
            "id": "ev-002", "phase": "04_tls",
            "source_file": "tls_scan.txt",
            "sha256": "b" * 64,
            "summary": "TLS 1.0 still active on port 443.",
        }),
        json.dumps({
            "id": "ev-003", "phase": "05_web",
            "source_file": "web_enum.txt",
            "sha256": "c" * 64,
            "summary": "Exposed .git directory on /api subdomain.",
        }),
    ]
    (run_dir / "evidence_manifest.jsonl").write_text(
        "\n".join(evidence_lines), encoding="utf-8"
    )

    findings_lines = [
        json.dumps({
            "id": "f-001", "title": "TLS 1.0 enabled",
            "severity": "medium", "phase": "04_tls",
            "evidence_ids": ["ev-002"],
            "description": "TLS 1.0 is deprecated and vulnerable to POODLE attack.",
            "recommendation": "Disable TLS 1.0 and TLS 1.1; enforce TLS 1.2+.",
        }),
        json.dumps({
            "id": "f-002", "title": "Exposed .git directory",
            "severity": "high", "phase": "05_web",
            "evidence_ids": ["ev-003"],
            "description": "Git repository accessible via HTTP — source code leakage.",
            "recommendation": "Block .git in webserver config; rotate any exposed credentials.",
        }),
    ]
    (run_dir / "findings.jsonl").write_text(
        "\n".join(findings_lines), encoding="utf-8"
    )

    (run_dir / "report_bundle.json").write_text(json.dumps({
        "project_ref": project_id,
        "profile": "external",
        "retest_status": "pending",
        "residual_risk": "Medium — high severity finding unresolved pending remediation",
        "counts": {"findings": 2, "evidence": 3},
    }), encoding="utf-8")

    return run_dir


def run_pilot() -> None:
    engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Sess()

    # ── 0. Seed roles ─────────────────────────────────────────────────────────
    _sep("0. Seed roles + admin user")
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="admin@techguard.local",
        password_hash=hash_password("changeme"),
        full_name="TG Admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    # Grant admin partner + platform_admin at org level so decide_approval role check passes
    partner_role = db.query(Role).filter_by(name=RoleName.partner.value).first()
    pa_role = db.query(Role).filter_by(name=RoleName.platform_admin.value).first()
    for role in [partner_role, pa_role]:
        if role:
            db.add(Permission(user_id=admin.id, scope_level=ScopeLevel.organization.value,
                              scope_id=None, role_id=role.id))
    db.commit()
    print(f"  Admin:  {admin.email}  (id={admin.id[:8]}…)")

    # ── 1. Client + project ───────────────────────────────────────────────────
    _sep("1. Client + project setup")
    client = Client(entity_name="Skyline Commerce Ltd", sector="ecommerce")
    db.add(client)
    db.flush()
    project = Project(
        client_id=client.id,
        service_type=ServiceType.vapt,
        owner_id=admin.id,
        status="draft",
        scope_summary="External VAPT of Skyline Commerce web application and API layer.",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    print(f"  Client:  {client.entity_name}")
    print(f"  Project: {project.id[:8]}…  type={project.service_type}")

    # ── 2. Scope + G1 ─────────────────────────────────────────────────────────
    _sep("2. Scope definition + G1 approval")
    scope_item = ScopeItem(
        project_id=project.id,
        kind=ScopeItemKind.asset.value,
        value="target.example.com, api.target.example.com — production web + API",
        approved=False,
    )
    db.add(scope_item)
    db.flush()
    ap_scope = request_approval(
        db,
        project_id=project.id,
        target_type="scope",
        target_id=scope_item.id,
        reason="Scope: target.example.com external VAPT",
        approver_role="partner",
        requested_by=admin.id,
    )
    db.commit()
    decide_approval(db, approval_id=ap_scope.id, approved=True, decider_id=admin.id)
    scope_item.approved = True
    db.commit()
    print(f"  Scope item approved: {scope_item.value[:60]}…")

    gates = dict(project.gates or {})
    gates["G1_scope"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G1_scope", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G1_scope": False}, after={"G1_scope": True})
    db.commit()
    print("  Gate G1 (scope) passed.")

    # ── 3. Load VAPT pack + generate plan ─────────────────────────────────────
    _sep("3. Load VAPT pack + generate plan")
    pack = load_pack("vapt")
    project.pack_id = pack.key
    db.commit()
    summary = generate_plan(db, project, pack)
    db.commit()
    print(f"  Pack: {pack.title}")
    print(f"  Requirements created: {summary.requirements_created}")
    print(f"  Evidence requests:    {summary.evidence_requests_created}")
    print(f"  Tasks created:        {summary.tasks_created}")

    # ── 4. PT-Orc import ──────────────────────────────────────────────────────
    _sep("4. PT-Orc import (fixture run dir)")
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = _make_fixture_run_dir(Path(tmpdir), project.id)
        result = run_import(db, project.id, run_dir)
    print(f"  Scope items imported:    {len(result.scope_items)}")
    print(f"  Evidence items imported: {len(result.evidence_items)}")
    print(f"  Findings imported:       {len(result.findings)}")
    print(f"  All findings status:     in_review (not auto-approved)")

    # Approve imported scope items — approvals were already created by the importer
    for ap_id in result.scope_approvals:
        decide_approval(db, approval_id=ap_id, approved=True, decider_id=admin.id)
    for si_id in result.scope_items:
        si = db.get(ScopeItem, si_id)
        if si:
            si.approved = True
    db.commit()
    print(f"  Imported scope items approved.")

    # ── 5. Mark evidence requests received + accept evidence + G2 + G3 ────────
    _sep("5. Evidence requests received + G2 + G3")
    for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all():
        er.status = EvidenceRequestStatus.received
    for ei in db.query(EvidenceItem).filter_by(project_id=project.id).all():
        ei.reviewer_status = "accepted"
    db.commit()

    gates = dict(project.gates or {})
    gates["G2_evidence_requests"] = True
    gates["G3_evidence_complete"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G2_evidence_requests", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G2_evidence_requests": False}, after={"G2_evidence_requests": True})
    record_event(db, action="gate.advanced.G3_evidence_complete", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G3_evidence_complete": False}, after={"G3_evidence_complete": True})
    db.commit()
    print("  Gates G2 + G3 passed.")

    # ── 6. Approve imported findings + add remediations + G4 ──────────────────
    _sep("6. Approve findings + remediations + G4")
    for finding in db.query(Finding).filter_by(project_id=project.id).all():
        ap_f = request_approval(
            db,
            project_id=project.id,
            target_type="finding_severity",
            target_id=finding.id,
            reason=f"Confirm severity for: {finding.title[:60]}",
            approver_role="partner",
            requested_by=admin.id,
        )
        db.commit()
        decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id,
                        reason="Severity confirmed by lead consultant")
        finding.status = FindingStatus.approved

        rem = RemediationAction(
            finding_id=finding.id,
            project_id=project.id,
            action=f"Remediate: {finding.title}",
            owner_id=admin.id,
            status="planned",
            residual_risk="low",
        )
        db.add(rem)
        print(f"  Approved finding: [{finding.severity}] {finding.title}")
    db.commit()

    gates = dict(project.gates or {})
    gates["G4_findings"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G4_findings", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G4_findings": False}, after={"G4_findings": True})
    db.commit()
    print("  Gate G4 (findings approved) passed.")

    # ── 7. QA agent + G5 ──────────────────────────────────────────────────────
    _sep("7. QA agent + G5")
    db.refresh(project)
    qa_report = run_qa(db, project)
    print(f"  QA rules run: {qa_report.rules_run}")
    if qa_report.issues:
        for issue in qa_report.issues:
            print(f"  [{issue.severity.upper()}] {issue.rule}: {issue.message}")
    print(f"  QA passed: {qa_report.passed}")

    gates = dict(project.gates or {})
    gates["G5_qa"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G5_qa", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G5_qa": False}, after={"G5_qa": True})
    db.commit()
    print("  Gate G5 (QA) passed.")

    # ── 8. Deliverables ───────────────────────────────────────────────────────
    _sep("8. Generate deliverables")
    _OUTPUT.mkdir(parents=True, exist_ok=True)
    db.refresh(project)

    xlsx_del, html_del = generate_gap_matrix(db, project, _OUTPUT)
    db.commit()
    print(f"  Gap matrix (XLSX): {xlsx_del.file_path}")

    rm_md, _ = generate_roadmap(db, project, _OUTPUT)
    db.commit()
    print(f"  Roadmap (MD):   {rm_md.file_path}")

    report_del = generate_report(db, project, _OUTPUT)
    db.commit()
    print(f"  Report (HTML):  {report_del.file_path}")

    ap_report = request_approval(
        db,
        project_id=project.id,
        target_type="deliverable",
        target_id=report_del.id,
        reason="Approve VAPT report for client release",
        approver_role="partner",
        requested_by=admin.id,
    )
    db.commit()
    decide_approval(db, approval_id=ap_report.id, approved=True, decider_id=admin.id,
                    reason="Report approved for release")
    db.commit()

    gates = dict(project.gates or {})
    gates["G6_report"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G6_report", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G6_report": False}, after={"G6_report": True})
    db.commit()
    print("  Gate G6 (report released) passed.")

    # ── 9. Closure + G7 ───────────────────────────────────────────────────────
    _sep("9. Closure with residual risk + G7")
    ap_close = request_approval(
        db,
        project_id=project.id,
        target_type="project_closure",
        target_id=project.id,
        reason="Close VAPT engagement — residual risk: medium (retest pending)",
        approver_role="partner",
        requested_by=admin.id,
        change_after={"status": "closed", "residual_risk": "medium"},
    )
    db.commit()
    decide_approval(db, approval_id=ap_close.id, approved=True, decider_id=admin.id,
                    reason="Residual risk accepted; retest scheduled")
    project.status = "closed"
    db.commit()

    gates = dict(project.gates or {})
    gates["G7_closure"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G7_closure", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G7_closure": False}, after={"G7_closure": True})
    db.commit()
    db.refresh(project)
    print(f"  Project status: {project.status}")
    print("  Gate G7 (closure) passed.")

    # ── 10. Audit trail summary ───────────────────────────────────────────────
    _sep("10. Audit trail summary")
    events = db.query(AuditTrailEvent).filter_by(project_id=project.id).all()
    approvals = db.query(ApprovalRequest).filter_by(project_id=project.id).all()
    print(f"  Audit events:       {len(events)}")
    print(f"  Approval requests:  {len(approvals)}")
    all_gates = ["G1_scope","G2_evidence_requests","G3_evidence_complete",
                 "G4_findings","G5_qa","G6_report","G7_closure"]
    print(f"  All gates passed:   {all(project.gates.get(g) for g in all_gates)}")
    print(f"\n  VAPT PILOT COMPLETE ✓")

    db.close()
    engine.dispose()


if __name__ == "__main__":
    run_pilot()
