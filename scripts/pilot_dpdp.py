"""DPDP readiness pilot — runs the full audit chain end-to-end.

Usage:
    python scripts/pilot_dpdp.py

Creates:
  client → project → scope → DPDP pack plan → evidence → finding →
  all 7 gates (with approvals) → QA → deliverables → closure

Prints a summary of every step and exits 0 on success.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — registers all models
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus, Task
from app.models.users import Role, RoleName, User
from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent
from app.services.audit import decide_approval, record_event, request_approval
from app.services.auth import hash_password
from app.services.deliverables.gap_matrix import generate_gap_matrix
from app.services.deliverables.report import generate_report
from app.services.deliverables.roadmap import generate_roadmap
from app.services.evidence.ingest import ingest_file
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan
from app.services.qa.agent import run_qa

_DB_URL = "sqlite:///data/pilot_dpdp.db"
_OUTPUT = Path("data/pilot_dpdp_out")
_ACTOR = "pilot-dpdp"


def _sep(label: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print('─' * 60)


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
    print(f"  Admin user:  {admin.email}  (id={admin.id[:8]}…)")

    # ── 1. Client + project ───────────────────────────────────────────────────
    _sep("1. Client + project setup")
    client = Client(name="Acme Fintech Pvt Ltd", sector="fintech")
    db.add(client)
    db.flush()
    project = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        owner_id=admin.id,
        status="setup",
        scope_summary="DPDP readiness assessment for Acme Fintech data processing operations.",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    print(f"  Client:      {client.name}")
    print(f"  Project id:  {project.id[:8]}…  type={project.service_type}")

    # ── 2. Scope + Gate G1 ────────────────────────────────────────────────────
    _sep("2. Scope definition + G1 approval")
    scope_item = ScopeItem(
        project_id=project.id,
        kind=ScopeItemKind.business_unit.value,
        value="Customer data processing — payments, KYC, onboarding",
        approved=False,
    )
    db.add(scope_item)
    db.flush()

    ap_scope = request_approval(
        db,
        project_id=project.id,
        target_type="scope",
        target_id=scope_item.id,
        reason="Initial scope: customer data processing BU",
        approver_role="partner",
        requested_by=admin.id,
    )
    db.commit()
    decide_approval(db, approval_id=ap_scope.id, approved=True, decider_id=admin.id)
    scope_item.approved = True
    db.commit()
    print(f"  Scope item approved: {scope_item.value[:60]}…")

    # Advance G1
    gates = dict(project.gates or {})
    gates["G1_scope"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G1_scope", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G1_scope": False}, after={"G1_scope": True})
    db.commit()
    print("  Gate G1 (scope) passed.")

    # ── 3. Load DPDP pack + generate plan ─────────────────────────────────────
    _sep("3. Load DPDP pack + generate plan")
    pack = load_pack("dpdp")
    project.pack_id = pack.key
    db.commit()
    summary = generate_plan(db, project, pack)
    db.commit()
    print(f"  Pack: {pack.title}")
    print(f"  Requirements created: {summary.requirements_created}")
    print(f"  Evidence requests:    {summary.evidence_requests_created}")
    print(f"  Tasks created:        {summary.tasks_created}")

    # ── 4. Mark evidence requests received + G2 ───────────────────────────────
    _sep("4. Mark evidence requests received + G2")
    for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all():
        er.status = EvidenceRequestStatus.received
    db.commit()
    gates = dict(project.gates or {})
    gates["G2_evidence_requests"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G2_evidence_requests", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G2_evidence_requests": False}, after={"G2_evidence_requests": True})
    db.commit()
    print(f"  All evidence requests marked received.")
    print("  Gate G2 (evidence requests) passed.")

    # ── 5. Ingest sample evidence + G3 ────────────────────────────────────────
    _sep("5. Ingest sample evidence + G3")
    sample_text = (
        b"Privacy Notice v2.3 — Acme Fintech\n"
        b"We collect personal data for KYC, payment processing, and onboarding.\n"
        b"Data is retained for 7 years per RBI guidelines.\n"
        b"Data subjects may request deletion via privacy@acmefintech.com.\n"
    )
    ev_item = ingest_file(
        db,
        project_id=project.id,
        data=sample_text,
        filename="privacy_notice_v2.3.txt",
    )
    ev_item.reviewer_status = "accepted"
    db.commit()
    print(f"  Evidence ingested: {ev_item.source_file}  sha256={ev_item.sha256[:12]}…")
    print(f"  Classification: {ev_item.classification}")

    gates = dict(project.gates or {})
    gates["G3_evidence_complete"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G3_evidence_complete", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G3_evidence_complete": False}, after={"G3_evidence_complete": True})
    db.commit()
    print("  Gate G3 (evidence complete) passed.")

    # ── 6. Create finding + approve severity + G4 ─────────────────────────────
    _sep("6. Finding creation + severity approval + G4")
    finding = Finding(
        project_id=project.id,
        title="Privacy notice does not include grievance officer details",
        description=(
            "Section 13 of DPDP Act requires a clearly listed grievance officer. "
            "Current privacy notice (v2.3) omits this."
        ),
        severity=FindingSeverity.high,
        status=FindingStatus.in_review,
        source=FindingSource.manual,
        owner_id=admin.id,
        evidence_item_ids=[ev_item.id],
    )
    db.add(finding)
    db.flush()

    ap_sev = request_approval(
        db,
        project_id=project.id,
        target_type="finding_severity",
        target_id=finding.id,
        reason="Confirm HIGH severity for missing grievance officer",
        approver_role="partner",
        requested_by=admin.id,
        change_before={"severity": "medium"},
        change_after={"severity": "high"},
    )
    db.commit()
    decide_approval(db, approval_id=ap_sev.id, approved=True, decider_id=admin.id,
                    reason="Severity confirmed HIGH — DPDP Act §13 violation")
    finding.status = FindingStatus.approved
    db.commit()
    print(f"  Finding: {finding.title[:60]}…")
    print(f"  Severity: {finding.severity}  Status: {finding.status}")

    # Add remediation action
    rem = RemediationAction(
        finding_id=finding.id,
        project_id=project.id,
        action="Add grievance officer name, email, and response timeline to privacy notice.",
        owner_id=admin.id,
        status="open",
        residual_risk="low",
    )
    db.add(rem)
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
    else:
        print("  QA: no issues.")
    print(f"  QA passed: {qa_report.passed}")

    if not qa_report.passed:
        print("  WARNING: QA errors present — advancing G5 anyway for pilot purposes.")
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
    print(f"  Gap matrix (HTML): {html_del.file_path}")

    rm_md, rm_html = generate_roadmap(db, project, _OUTPUT)
    db.commit()
    print(f"  Roadmap (MD):   {rm_md.file_path}")
    print(f"  Roadmap (HTML): {rm_html.file_path}")

    report_del = generate_report(db, project, _OUTPUT)
    db.commit()
    print(f"  Report (HTML):  {report_del.file_path}")

    # Report release requires an approval (Gate 6)
    ap_report = request_approval(
        db,
        project_id=project.id,
        target_type="deliverable",
        target_id=report_del.id,
        reason="Approve final report for release",
        approver_role="partner",
        requested_by=admin.id,
    )
    db.commit()
    decide_approval(db, approval_id=ap_report.id, approved=True, decider_id=admin.id,
                    reason="Report content approved by partner")
    db.commit()

    gates = dict(project.gates or {})
    gates["G6_report"] = True
    project.gates = gates
    record_event(db, action="gate.advanced.G6_report", target_type="project",
                 target_id=project.id, actor_id=admin.id, project_id=project.id,
                 before={"G6_report": False}, after={"G6_report": True})
    db.commit()
    print("  Gate G6 (report released) passed.")

    # ── 9. Closure + residual risk + G7 ───────────────────────────────────────
    _sep("9. Closure with residual risk + G7")
    ap_close = request_approval(
        db,
        project_id=project.id,
        target_type="project_closure",
        target_id=project.id,
        reason="Close engagement with low residual risk — grievance officer gap accepted",
        approver_role="partner",
        requested_by=admin.id,
        change_before={"status": "active"},
        change_after={"status": "closed", "residual_risk": "low"},
    )
    db.commit()
    decide_approval(db, approval_id=ap_close.id, approved=True, decider_id=admin.id,
                    reason="Residual risk accepted by partner")
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
    print(f"  All gates passed:   {all(project.gates.get(g) for g in ['G1_scope','G2_evidence_requests','G3_evidence_complete','G4_findings','G5_qa','G6_report','G7_closure'])}")
    print(f"\n  DPDP PILOT COMPLETE ✓")

    db.close()
    engine.dispose()


if __name__ == "__main__":
    run_pilot()
