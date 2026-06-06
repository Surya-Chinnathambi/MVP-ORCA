"""Full-system multi-pack pilot — one client, three concurrent service lines.

Usage:
    python scripts/pilot_full.py

Runs end-to-end through all 7 review gates for:
  1. DPDP readiness assessment
  2. VAPT external assessment (PT-Orc import)
  3. ISO 27001 readiness review

All three share a single DB and a single client, demonstrating that
DPDP, VAPT, and GRC methodology packs operate on the same platform
with full audit trail, approval gateway, and deliverable pipeline.

Import-only rule: the VAPT track imports findings from PT-Orc; the
orchestrator never executes scans or exploits.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
from app.models.organization import Organization
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus
from app.models.users import Role, RoleName, User
from app.models.workflow import ApprovalRequest, AuditTrailEvent
from app.services.audit import decide_approval, record_event, request_approval
from app.services.auth import hash_password
from app.services.deliverables.gap_matrix import generate_gap_matrix
from app.services.deliverables.management_summary import generate_management_summary
from app.services.deliverables.report import generate_report
from app.services.deliverables.roadmap import generate_roadmap
from app.services.evidence.ingest import ingest_file
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan
from app.services.qa.agent import run_qa
from ptorc_adapter.importer import run_import

_DB_URL = "sqlite:///data/pilot_full.db"
_OUTPUT = Path("data/pilot_full_out")
_ALL_GATES = [
    "G1_scope", "G2_evidence_requests", "G3_evidence_complete",
    "G4_findings", "G5_qa", "G6_report", "G7_closure",
]


def _sep(label: str) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {label}")
    print('═' * 64)


def _step(label: str) -> None:
    print(f"\n  ── {label}")


def _advance_gate(db, project, gate: str, actor_id: str) -> None:
    gates = dict(project.gates or {})
    gates[gate] = True
    project.gates = gates
    record_event(db, action=f"gate.advanced.{gate}", target_type="project",
                 target_id=project.id, actor_id=actor_id, project_id=project.id,
                 before={gate: False}, after={gate: True})
    db.commit()
    print(f"  ✓ Gate {gate} passed.")


def _make_ptorc_run(tmp: Path, project_id: str) -> Path:
    d = tmp / "ptorc_run"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scope.json").write_text(json.dumps({
        "project_ref": project_id,
        "engagement_profile": "web",
        "testing_depth": "standard",
        "auth_level": "authenticated",
        "targets": ["app.demo.example.com"],
        "rules_of_engagement": "Authorised testing; no denial-of-service.",
        "window": {"start": "2026-06-01", "end": "2026-06-14"},
    }))
    (d / "evidence_manifest.jsonl").write_text("\n".join([
        json.dumps({"id": "ev-w01", "phase": "08_app_api", "source_file": "web_scan.txt",
                    "sha256": "a" * 64, "summary": "SQL injection probe results."}),
        json.dumps({"id": "ev-w02", "phase": "08_app_api", "source_file": "auth_check.txt",
                    "sha256": "b" * 64, "summary": "Weak session token entropy detected."}),
    ]))
    (d / "findings.jsonl").write_text("\n".join([
        json.dumps({"id": "f-w01", "title": "SQL injection — login endpoint",
                    "severity": "critical", "phase": "08_app_api",
                    "evidence_ids": ["ev-w01"],
                    "description": "Unsanitised input allows UNION-based SQLi.",
                    "recommendation": "Use parameterised queries; implement WAF rules."}),
        json.dumps({"id": "f-w02", "title": "Weak session token entropy",
                    "severity": "medium", "phase": "08_app_api",
                    "evidence_ids": ["ev-w02"],
                    "description": "Session tokens are 8 bytes — brute-forceable.",
                    "recommendation": "Use 128-bit cryptographically random tokens."}),
    ]))
    (d / "report_bundle.json").write_text(json.dumps({
        "project_ref": project_id, "profile": "web",
        "retest_status": "pending", "residual_risk": "Critical — SQLi unresolved",
        "counts": {"findings": 2, "evidence": 2},
    }))
    return d


# ── Project runners ───────────────────────────────────────────────────────────

def run_dpdp_project(db, client, admin, output: Path) -> Project:
    _sep("PROJECT 1 — DPDP Readiness Assessment")

    _step("1.1 Create project")
    project = Project(client_id=client.id, service_type=ServiceType.dpdp,
                      owner_id=admin.id, status="setup",
                      scope_summary="DPDP readiness for customer data processing.")
    db.add(project)
    db.commit(); db.refresh(project)
    print(f"  Project id: {project.id[:8]}…  type=dpdp")

    _step("1.2 Scope + G1")
    si = ScopeItem(project_id=project.id, kind=ScopeItemKind.business_unit.value,
                   value="Customer personal data — onboarding, payments, KYC", approved=False)
    db.add(si); db.flush()
    ap = request_approval(db, project_id=project.id, target_type="scope",
                          target_id=si.id, reason="Scope: customer BU",
                          approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap.id, approved=True, decider_id=admin.id)
    si.approved = True; db.commit()
    _advance_gate(db, project, "G1_scope", admin.id)

    _step("1.3 Load DPDP pack + plan")
    pack = load_pack("dpdp")
    project.pack_id = pack.key; db.commit()
    summary = generate_plan(db, project, pack); db.commit()
    print(f"  {summary.requirements_created} reqs, {summary.evidence_requests_created} ERs, {summary.tasks_created} tasks")

    _step("1.4 Evidence requests received + G2")
    for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all():
        er.status = EvidenceRequestStatus.received
    db.commit(); _advance_gate(db, project, "G2_evidence_requests", admin.id)

    _step("1.5 Ingest evidence + G3")
    ev = ingest_file(db, project_id=project.id,
                     data=b"DPDP privacy notice: grievance officer: dpo@demo.com; retention 7yr",
                     filename="privacy_notice.txt")
    ev.reviewer_status = "accepted"; db.commit()
    print(f"  Evidence ingested: {ev.source_file} ({ev.classification})")
    _advance_gate(db, project, "G3_evidence_complete", admin.id)

    _step("1.6 Finding + severity approval + G4")
    f = Finding(project_id=project.id,
                title="Privacy notice missing grievance officer contact",
                description="DPDP §13 requires a named grievance officer with contact details.",
                severity=FindingSeverity.high, status=FindingStatus.in_review,
                source=FindingSource.manual, owner_id=admin.id,
                evidence_item_ids=[ev.id])
    db.add(f); db.flush()
    ap_f = request_approval(db, project_id=project.id, target_type="finding_severity",
                            target_id=f.id, reason="Confirm HIGH for missing GO details",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
    f.status = FindingStatus.approved
    db.add(RemediationAction(finding_id=f.id, project_id=project.id,
                             action="Add grievance officer to privacy notice",
                             owner_id=admin.id, status="open", residual_risk="low"))
    db.commit(); _advance_gate(db, project, "G4_findings", admin.id)

    _step("1.7 QA + G5")
    db.refresh(project); qa = run_qa(db, project)
    print(f"  QA: {qa.rules_run} rules, passed={qa.passed}")
    _advance_gate(db, project, "G5_qa", admin.id)

    _step("1.8 Deliverables + G6")
    out = output / "dpdp"; out.mkdir(parents=True, exist_ok=True)
    db.refresh(project)
    generate_gap_matrix(db, project, out); db.commit()
    generate_roadmap(db, project, out); db.commit()
    report = generate_report(db, project, out); db.commit()
    ap_r = request_approval(db, project_id=project.id, target_type="deliverable",
                            target_id=report.id, reason="Release DPDP report",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_r.id, approved=True, decider_id=admin.id)
    db.commit(); _advance_gate(db, project, "G6_report", admin.id)

    _step("1.9 Closure + G7")
    ap_cl = request_approval(db, project_id=project.id, target_type="project_closure",
                             target_id=project.id, reason="Close DPDP engagement",
                             approver_role="partner", requested_by=admin.id,
                             change_after={"status": "closed"})
    db.commit(); decide_approval(db, approval_id=ap_cl.id, approved=True, decider_id=admin.id)
    project.status = "closed"; db.commit()
    _advance_gate(db, project, "G7_closure", admin.id)

    return project


def run_vapt_project(db, client, admin, output: Path) -> Project:
    _sep("PROJECT 2 — VAPT Web Application Assessment (PT-Orc import)")

    _step("2.1 Create project")
    project = Project(client_id=client.id, service_type=ServiceType.vapt,
                      owner_id=admin.id, status="setup",
                      scope_summary="Authenticated web app VAPT via PT-Orc v2 import.")
    db.add(project)
    db.commit(); db.refresh(project)
    print(f"  Project id: {project.id[:8]}…  type=vapt")

    _step("2.2 Scope + G1")
    si = ScopeItem(project_id=project.id, kind=ScopeItemKind.asset.value,
                   value="app.demo.example.com — authenticated web app", approved=False)
    db.add(si); db.flush()
    ap = request_approval(db, project_id=project.id, target_type="scope",
                          target_id=si.id, reason="Scope: web application",
                          approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap.id, approved=True, decider_id=admin.id)
    si.approved = True; db.commit()
    _advance_gate(db, project, "G1_scope", admin.id)

    _step("2.3 Load VAPT pack + plan")
    pack = load_pack("vapt")
    project.pack_id = pack.key; db.commit()
    summary = generate_plan(db, project, pack); db.commit()
    print(f"  {summary.requirements_created} reqs, {summary.evidence_requests_created} ERs")

    _step("2.4 PT-Orc import (import-only, never executes)")
    with tempfile.TemporaryDirectory() as td:
        run_dir = _make_ptorc_run(Path(td), project.id)
        result = run_import(db, project.id, run_dir)
    print(f"  Imported: {len(result.findings_created)} findings, {len(result.evidence_items)} evidence items")
    print(f"  All imported findings → status=in_review (not auto-approved ✓)")
    # Approve imported scope items (importer already created pending approvals)
    for ap_id in result.scope_approvals:
        decide_approval(db, approval_id=ap_id, approved=True, decider_id=admin.id)
    for sc_id in result.scope_items:
        sc = db.get(ScopeItem, sc_id)
        if sc:
            sc.approved = True
    db.commit()

    _step("2.5 Evidence + G2 + G3")
    for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all():
        er.status = EvidenceRequestStatus.received
    for ei in db.query(EvidenceItem).filter_by(project_id=project.id).all():
        ei.reviewer_status = "accepted"
    db.commit()
    _advance_gate(db, project, "G2_evidence_requests", admin.id)
    _advance_gate(db, project, "G3_evidence_complete", admin.id)

    _step("2.6 Approve findings + G4 (import-only: findings never auto-approved)")
    for finding in db.query(Finding).filter_by(project_id=project.id).all():
        ap_f = request_approval(db, project_id=project.id, target_type="finding_severity",
                                target_id=finding.id,
                                reason=f"Confirm {finding.severity} — {finding.title[:40]}",
                                approver_role="partner", requested_by=admin.id)
        db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
        finding.status = FindingStatus.approved
        db.add(RemediationAction(finding_id=finding.id, project_id=project.id,
                                 action=f"Remediate: {finding.title}",
                                 owner_id=admin.id, status="open", residual_risk="medium"))
        print(f"  Approved [{finding.severity}] {finding.title}")
    db.commit(); _advance_gate(db, project, "G4_findings", admin.id)

    _step("2.7 QA + G5")
    db.refresh(project); qa = run_qa(db, project)
    print(f"  QA: {qa.rules_run} rules, passed={qa.passed}")
    _advance_gate(db, project, "G5_qa", admin.id)

    _step("2.8 Deliverables + G6")
    out = output / "vapt"; out.mkdir(parents=True, exist_ok=True)
    db.refresh(project)
    generate_gap_matrix(db, project, out); db.commit()
    report = generate_report(db, project, out); db.commit()
    generate_management_summary(db, project, out); db.commit()
    ap_r = request_approval(db, project_id=project.id, target_type="deliverable",
                            target_id=report.id, reason="Release VAPT report",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_r.id, approved=True, decider_id=admin.id)
    db.commit(); _advance_gate(db, project, "G6_report", admin.id)

    _step("2.9 Closure + G7")
    ap_cl = request_approval(db, project_id=project.id, target_type="project_closure",
                             target_id=project.id, reason="Close VAPT engagement",
                             approver_role="partner", requested_by=admin.id,
                             change_after={"status": "closed", "residual_risk": "critical — SQLi open"})
    db.commit(); decide_approval(db, approval_id=ap_cl.id, approved=True, decider_id=admin.id)
    project.status = "closed"; db.commit()
    _advance_gate(db, project, "G7_closure", admin.id)

    return project


def run_iso_project(db, client, admin, output: Path) -> Project:
    _sep("PROJECT 3 — ISO 27001 Readiness Review")

    _step("3.1 Create project")
    project = Project(client_id=client.id, service_type=ServiceType.vapt,
                      owner_id=admin.id, status="setup",
                      scope_summary="ISO 27001 readiness review — ISMS scoping and gap analysis.")
    db.add(project)
    db.commit(); db.refresh(project)
    print(f"  Project id: {project.id[:8]}…  pack=iso_27001_readiness")

    _step("3.2 Scope + G1")
    si = ScopeItem(project_id=project.id, kind=ScopeItemKind.business_unit.value,
                   value="HQ information systems — all departments", approved=False)
    db.add(si); db.flush()
    ap = request_approval(db, project_id=project.id, target_type="scope",
                          target_id=si.id, reason="ISO 27001 ISMS scope: all HQ systems",
                          approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap.id, approved=True, decider_id=admin.id)
    si.approved = True; db.commit()
    _advance_gate(db, project, "G1_scope", admin.id)

    _step("3.3 Load ISO 27001 readiness pack + plan")
    pack = load_pack("iso_27001_readiness")
    project.pack_id = pack.key; db.commit()
    summary = generate_plan(db, project, pack); db.commit()
    print(f"  {summary.requirements_created} reqs, {summary.evidence_requests_created} ERs, {summary.tasks_created} tasks")

    _step("3.4 Evidence requests received + G2")
    for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all():
        er.status = EvidenceRequestStatus.received
    db.commit(); _advance_gate(db, project, "G2_evidence_requests", admin.id)

    _step("3.5 Ingest evidence + G3")
    ev = ingest_file(db, project_id=project.id,
                     data=b"ISMS Scope Statement v1.0 — covers all HQ systems per ISO 27001 clause 4.3",
                     filename="isms_scope_statement.txt")
    ev.reviewer_status = "accepted"; db.commit()
    print(f"  Evidence ingested: {ev.source_file}")
    _advance_gate(db, project, "G3_evidence_complete", admin.id)

    _step("3.6 Finding + G4")
    f = Finding(project_id=project.id,
                title="No formal risk treatment plan documented",
                description="Clause 6.1.3 requires a documented risk treatment plan.",
                severity=FindingSeverity.high, status=FindingStatus.in_review,
                source=FindingSource.manual, owner_id=admin.id,
                evidence_item_ids=[ev.id])
    db.add(f); db.flush()
    ap_f = request_approval(db, project_id=project.id, target_type="finding_severity",
                            target_id=f.id, reason="Confirm HIGH — missing risk treatment plan",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
    f.status = FindingStatus.approved
    db.add(RemediationAction(finding_id=f.id, project_id=project.id,
                             action="Draft and approve a risk treatment plan per ISO 27001 §6.1.3",
                             owner_id=admin.id, status="open", residual_risk="low"))
    db.commit(); _advance_gate(db, project, "G4_findings", admin.id)

    _step("3.7 QA + G5")
    db.refresh(project); qa = run_qa(db, project)
    print(f"  QA: {qa.rules_run} rules, passed={qa.passed}")
    _advance_gate(db, project, "G5_qa", admin.id)

    _step("3.8 Deliverables + G6")
    out = output / "iso27001"; out.mkdir(parents=True, exist_ok=True)
    db.refresh(project)
    generate_gap_matrix(db, project, out); db.commit()
    generate_roadmap(db, project, out); db.commit()
    report = generate_report(db, project, out); db.commit()
    ap_r = request_approval(db, project_id=project.id, target_type="deliverable",
                            target_id=report.id, reason="Release ISO 27001 readiness report",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_r.id, approved=True, decider_id=admin.id)
    db.commit(); _advance_gate(db, project, "G6_report", admin.id)

    _step("3.9 Closure + G7")
    ap_cl = request_approval(db, project_id=project.id, target_type="project_closure",
                             target_id=project.id, reason="Close ISO readiness engagement",
                             approver_role="partner", requested_by=admin.id,
                             change_after={"status": "closed"})
    db.commit(); decide_approval(db, approval_id=ap_cl.id, approved=True, decider_id=admin.id)
    project.status = "closed"; db.commit()
    _advance_gate(db, project, "G7_closure", admin.id)

    return project


# ── Main entry point ──────────────────────────────────────────────────────────

def run_pilot() -> None:
    engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Sess()

    _sep("0. Seed — roles + admin + org + client")
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(email="admin@techguard.local", password_hash=hash_password("changeme"),
                 full_name="TG Admin", is_active=True)
    db.add(admin); db.commit(); db.refresh(admin)
    org = Organization(name="TechGuard Labs")
    db.add(org); db.flush()
    client = Client(name="TechGuard Demo Corp", sector="technology", organization_id=org.id)
    db.add(client); db.commit(); db.refresh(client)
    print(f"  Admin: {admin.email}  |  Client: {client.entity_name}")

    _OUTPUT.mkdir(parents=True, exist_ok=True)

    proj_dpdp = run_dpdp_project(db, client, admin, _OUTPUT)
    proj_vapt = run_vapt_project(db, client, admin, _OUTPUT)
    proj_iso = run_iso_project(db, client, admin, _OUTPUT)

    # ── Final summary ─────────────────────────────────────────────────────────
    _sep("FULL-SYSTEM ACCEPTANCE SUMMARY")
    total_events = db.query(AuditTrailEvent).count()
    total_approvals = db.query(ApprovalRequest).count()
    projects = [proj_dpdp, proj_vapt, proj_iso]
    labels = ["DPDP", "VAPT", "ISO 27001"]

    print(f"\n  {'Project':<20} {'Pack':<25} {'Status':<10} {'Gates'}")
    print(f"  {'─'*70}")
    for proj, label in zip(projects, labels):
        db.refresh(proj)
        gates_ok = all(proj.gates.get(g) for g in _ALL_GATES)
        print(f"  {label:<20} {proj.pack_id or '':<25} {proj.status:<10} {'ALL ✓' if gates_ok else 'PARTIAL'}")

    print(f"\n  Total audit events:      {total_events}")
    print(f"  Total approval requests: {total_approvals}")
    print(f"  All projects closed:     {all(p.status == 'closed' for p in projects)}")
    print(f"  All gates passed:        {all(all(p.gates.get(g) for g in _ALL_GATES) for p in projects)}")
    print(f"\n  FULL PILOT COMPLETE ✓")

    db.close()
    engine.dispose()


if __name__ == "__main__":
    run_pilot()
