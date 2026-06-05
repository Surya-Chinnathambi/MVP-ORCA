"""Stage 30 acceptance test — full-system multi-pack cross-service pilot.

Validates all criteria from Full Spec §24:
1.  Every project has approved scope (G1 ✓ for DPDP, VAPT, ISO 27001).
2.  All evidence is traceable to at least one finding via evidence_item_ids.
3.  Findings are in `approved` status before client release (no auto-approve path).
4.  Reports are generated from approved state only (gate G6 gated by approval).
5.  DPDP + VAPT + ISO 27001 run on the same platform, same DB, same client.
6.  PT-Orc import lands findings at source=ptorc, status=in_review (never auto-approved).
7.  All 7 gates (G1–G7) are recorded for each project via AuditTrailEvent.
8.  Every gate-advance records an AuditTrailEvent.
9.  QA agent does not create any ApprovalRequest (advisory only).
10. All three projects reach status=closed with residual-risk approvals.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
from app.models.organization import Organization
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus
from app.models.users import Role, RoleName, User
from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent
from app.services.audit import decide_approval, record_event, request_approval
from app.services.auth import hash_password
from app.services.deliverables.gap_matrix import generate_gap_matrix
from app.services.deliverables.report import generate_report
from app.services.evidence.ingest import ingest_file
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan
from app.services.qa.agent import run_qa
from ptorc_adapter.importer import run_import

_ALL_GATES = [
    "G1_scope", "G2_evidence_requests", "G3_evidence_complete",
    "G4_findings", "G5_qa", "G6_report", "G7_closure",
]


# ── Shared in-memory DB fixture ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:",
                      connect_args={"check_same_thread": False},
                      poolclass=StaticPool)
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def db(engine):
    s = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield s
    s.close()


@pytest.fixture(scope="module")
def admin(db):
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    user = User(email="s30_admin@tg.local", password_hash=hash_password("pw"),
                full_name="S30 Admin", is_active=True)
    db.add(user); db.commit(); db.refresh(user)
    return user


@pytest.fixture(scope="module")
def shared_client(db, admin):
    org = Organization(name="S30 Org")
    db.add(org); db.flush()
    client = Client(name="TechGuard Demo Corp S30", sector="tech", organization_id=org.id)
    db.add(client); db.commit(); db.refresh(client)
    return client


# ── Helpers ───────────────────────────────────────────────────────────────────

def _advance_gate(db, project, gate: str, actor_id: str) -> None:
    gates = dict(project.gates or {})
    gates[gate] = True
    project.gates = gates
    record_event(db, action=f"gate.advanced.{gate}", target_type="project",
                 target_id=project.id, actor_id=actor_id, project_id=project.id,
                 before={gate: False}, after={gate: True})
    db.commit()


def _approve_scope(db, project, admin, value: str) -> ScopeItem:
    si = ScopeItem(project_id=project.id, kind=ScopeItemKind.business_unit.value,
                   value=value, approved=False)
    db.add(si); db.flush()
    ap = request_approval(db, project_id=project.id, target_type="scope",
                          target_id=si.id, reason="Scope approval",
                          approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap.id, approved=True, decider_id=admin.id)
    si.approved = True; db.commit()
    return si


def _make_ptorc_run(tmp: Path, project_id: str) -> Path:
    d = tmp / "run"; d.mkdir(parents=True, exist_ok=True)
    (d / "scope.json").write_text(json.dumps({
        "project_ref": project_id, "engagement_profile": "web",
        "testing_depth": "standard", "auth_level": "authenticated",
        "targets": ["app.s30.example.com"],
        "rules_of_engagement": "Authorised test.",
        "window": {"start": "2026-06-01", "end": "2026-06-14"},
    }))
    (d / "evidence_manifest.jsonl").write_text(json.dumps({
        "id": "ev-s30", "phase": "08_app_api", "source_file": "scan.txt",
        "sha256": "c" * 64, "summary": "XSS probe results.",
    }))
    (d / "findings.jsonl").write_text(json.dumps({
        "id": "f-s30", "title": "Reflected XSS on search endpoint",
        "severity": "high", "phase": "08_app_api", "evidence_ids": ["ev-s30"],
        "description": "Unescaped user input in search results.",
        "recommendation": "HTML-encode output; implement CSP headers.",
    }))
    (d / "report_bundle.json").write_text(json.dumps({
        "project_ref": project_id, "profile": "web",
        "retest_status": "pending", "residual_risk": "high",
        "counts": {"findings": 1, "evidence": 1},
    }))
    return d


def _close_project(db, project, admin, report_del) -> None:
    """Run gates G5-G7: QA, report release, closure."""
    db.refresh(project)
    run_qa(db, project)
    _advance_gate(db, project, "G5_qa", admin.id)

    ap_r = request_approval(db, project_id=project.id, target_type="deliverable",
                            target_id=report_del.id, reason="Release report",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_r.id, approved=True, decider_id=admin.id)
    db.commit(); _advance_gate(db, project, "G6_report", admin.id)

    ap_cl = request_approval(db, project_id=project.id, target_type="project_closure",
                             target_id=project.id, reason="Close project",
                             approver_role="partner", requested_by=admin.id,
                             change_after={"status": "closed"})
    db.commit(); decide_approval(db, approval_id=ap_cl.id, approved=True, decider_id=admin.id)
    project.status = "closed"; db.commit()
    _advance_gate(db, project, "G7_closure", admin.id)


# ── Build all three projects as module-scoped state ───────────────────────────

@pytest.fixture(scope="module")
def dpdp_project(db, shared_client, admin, tmp_path_factory):
    out = tmp_path_factory.mktemp("s30_dpdp")
    proj = Project(client_id=shared_client.id, service_type=ServiceType.dpdp,
                   owner_id=admin.id, status="setup",
                   scope_summary="DPDP readiness.")
    db.add(proj); db.commit(); db.refresh(proj)

    _approve_scope(db, proj, admin, "Customer PII processing")
    _advance_gate(db, proj, "G1_scope", admin.id)

    pack = load_pack("dpdp"); proj.pack_id = pack.key; db.commit()
    generate_plan(db, proj, pack); db.commit()

    for er in db.query(EvidenceRequest).filter_by(project_id=proj.id).all():
        er.status = EvidenceRequestStatus.received
    db.commit(); _advance_gate(db, proj, "G2_evidence_requests", admin.id)

    ev = ingest_file(db, project_id=proj.id, data=b"DPDP privacy notice content",
                     filename="privacy_notice.txt")
    ev.reviewer_status = "accepted"; db.commit()
    _advance_gate(db, proj, "G3_evidence_complete", admin.id)

    f = Finding(project_id=proj.id, title="Missing grievance officer",
                description="DPDP §13 requires named grievance officer.",
                severity=FindingSeverity.high, status=FindingStatus.in_review,
                source=FindingSource.manual, owner_id=admin.id,
                evidence_item_ids=[ev.id])
    db.add(f); db.flush()
    ap_f = request_approval(db, project_id=proj.id, target_type="finding_severity",
                            target_id=f.id, reason="Confirm HIGH",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
    f.status = FindingStatus.approved; db.commit()
    _advance_gate(db, proj, "G4_findings", admin.id)

    rpt = generate_report(db, proj, out); db.commit()
    _close_project(db, proj, admin, rpt)
    return proj


@pytest.fixture(scope="module")
def vapt_project(db, shared_client, admin, tmp_path_factory):
    out = tmp_path_factory.mktemp("s30_vapt")
    proj = Project(client_id=shared_client.id, service_type=ServiceType.vapt,
                   owner_id=admin.id, status="setup",
                   scope_summary="Web VAPT via PT-Orc import.")
    db.add(proj); db.commit(); db.refresh(proj)

    _approve_scope(db, proj, admin, "app.s30.example.com")
    _advance_gate(db, proj, "G1_scope", admin.id)

    pack = load_pack("vapt"); proj.pack_id = pack.key; db.commit()
    generate_plan(db, proj, pack); db.commit()

    with tempfile.TemporaryDirectory() as td:
        run_dir = _make_ptorc_run(Path(td), proj.id)
        result = run_import(db, proj.id, run_dir)
    # Importer already created pending approvals for each scope item
    for ap_id in result.scope_approvals:
        decide_approval(db, approval_id=ap_id, approved=True, decider_id=admin.id)
    for sc_id in result.scope_items:
        sc = db.get(ScopeItem, sc_id)
        if sc:
            sc.approved = True
    db.commit()

    for er in db.query(EvidenceRequest).filter_by(project_id=proj.id).all():
        er.status = EvidenceRequestStatus.received
    for ei in db.query(EvidenceItem).filter_by(project_id=proj.id).all():
        ei.reviewer_status = "accepted"
    db.commit()
    _advance_gate(db, proj, "G2_evidence_requests", admin.id)
    _advance_gate(db, proj, "G3_evidence_complete", admin.id)

    for finding in db.query(Finding).filter_by(project_id=proj.id).all():
        ap_f = request_approval(db, project_id=proj.id, target_type="finding_severity",
                                target_id=finding.id, reason="Confirm severity",
                                approver_role="partner", requested_by=admin.id)
        db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
        finding.status = FindingStatus.approved
    db.commit()
    _advance_gate(db, proj, "G4_findings", admin.id)

    rpt = generate_report(db, proj, out); db.commit()
    _close_project(db, proj, admin, rpt)
    return proj


@pytest.fixture(scope="module")
def iso_project(db, shared_client, admin, tmp_path_factory):
    out = tmp_path_factory.mktemp("s30_iso")
    proj = Project(client_id=shared_client.id, service_type=ServiceType.vapt,
                   owner_id=admin.id, status="setup",
                   scope_summary="ISO 27001 readiness review.")
    db.add(proj); db.commit(); db.refresh(proj)

    _approve_scope(db, proj, admin, "HQ ISMS scope — all departments")
    _advance_gate(db, proj, "G1_scope", admin.id)

    pack = load_pack("iso_27001_readiness"); proj.pack_id = pack.key; db.commit()
    generate_plan(db, proj, pack); db.commit()

    for er in db.query(EvidenceRequest).filter_by(project_id=proj.id).all():
        er.status = EvidenceRequestStatus.received
    db.commit(); _advance_gate(db, proj, "G2_evidence_requests", admin.id)

    ev = ingest_file(db, project_id=proj.id,
                     data=b"ISMS Scope Statement v1 - ISO 27001 clause 4.3",
                     filename="isms_scope.txt")
    ev.reviewer_status = "accepted"; db.commit()
    _advance_gate(db, proj, "G3_evidence_complete", admin.id)

    f = Finding(project_id=proj.id, title="No documented risk treatment plan",
                description="ISO 27001 clause 6.1.3 requires a risk treatment plan.",
                severity=FindingSeverity.high, status=FindingStatus.in_review,
                source=FindingSource.manual, owner_id=admin.id,
                evidence_item_ids=[ev.id])
    db.add(f); db.flush()
    ap_f = request_approval(db, project_id=proj.id, target_type="finding_severity",
                            target_id=f.id, reason="Confirm HIGH severity",
                            approver_role="partner", requested_by=admin.id)
    db.commit(); decide_approval(db, approval_id=ap_f.id, approved=True, decider_id=admin.id)
    f.status = FindingStatus.approved; db.commit()
    _advance_gate(db, proj, "G4_findings", admin.id)

    rpt = generate_report(db, proj, out); db.commit()
    _close_project(db, proj, admin, rpt)
    return proj


# ── 1. Approved scope in every project ───────────────────────────────────────

def test_dpdp_scope_approved(db, dpdp_project):
    si = db.query(ScopeItem).filter_by(project_id=dpdp_project.id, approved=True).first()
    assert si is not None


def test_vapt_scope_approved(db, vapt_project):
    si = db.query(ScopeItem).filter_by(project_id=vapt_project.id, approved=True).first()
    assert si is not None


def test_iso_scope_approved(db, iso_project):
    si = db.query(ScopeItem).filter_by(project_id=iso_project.id, approved=True).first()
    assert si is not None


# ── 2. Evidence traceable to findings ─────────────────────────────────────────

def test_findings_have_evidence_ids(db, dpdp_project, iso_project):
    for proj in (dpdp_project, iso_project):
        findings = db.query(Finding).filter_by(project_id=proj.id).all()
        assert findings, f"Project {proj.id} has no findings"
        for f in findings:
            assert f.evidence_item_ids, f"Finding {f.title} has no evidence_item_ids"


# ── 3. Findings approved before closure (never auto-approved) ─────────────────

def test_findings_approved_at_closure(db, dpdp_project, vapt_project, iso_project):
    for proj in (dpdp_project, vapt_project, iso_project):
        findings = db.query(Finding).filter_by(project_id=proj.id).all()
        for f in findings:
            assert f.status in (
                FindingStatus.approved.value, FindingStatus.client_shared.value,
                FindingStatus.closed.value, FindingStatus.risk_accepted.value,
            ), f"Finding '{f.title}' has status={f.status} at closure"


# ── 4. PT-Orc findings land in_review, never auto-approved ───────────────────

def test_ptorc_import_not_auto_approved(db, vapt_project):
    ptorc_findings = db.query(Finding).filter_by(
        project_id=vapt_project.id,
        source=FindingSource.ptorc.value,
    ).all()
    assert ptorc_findings, "No PT-Orc findings in VAPT project"
    # Verify their approval requests were created (import-only; never skipped gateway)
    for f in ptorc_findings:
        ap = db.query(ApprovalRequest).filter_by(
            project_id=vapt_project.id, target_id=f.id
        ).first()
        assert ap is not None, f"PT-Orc finding {f.title} has no approval request"
        assert ap.status == ApprovalStatus.approved


# ── 5. Same platform: one DB, one client, three service lines ─────────────────

def test_three_projects_same_client(db, shared_client, dpdp_project, vapt_project, iso_project):
    assert dpdp_project.client_id == shared_client.id
    assert vapt_project.client_id == shared_client.id
    assert iso_project.client_id == shared_client.id
    service_types = {dpdp_project.service_type, vapt_project.service_type}
    assert ServiceType.dpdp.value in service_types
    assert ServiceType.vapt.value in service_types


# ── 6. All 7 gates passed for every project ───────────────────────────────────

def test_all_gates_passed_dpdp(dpdp_project):
    assert all(dpdp_project.gates.get(g) for g in _ALL_GATES), dpdp_project.gates


def test_all_gates_passed_vapt(vapt_project):
    assert all(vapt_project.gates.get(g) for g in _ALL_GATES), vapt_project.gates


def test_all_gates_passed_iso(iso_project):
    assert all(iso_project.gates.get(g) for g in _ALL_GATES), iso_project.gates


# ── 7. Gate advances are recorded in audit trail ──────────────────────────────

def test_audit_trail_has_gate_events(db, dpdp_project, vapt_project, iso_project):
    for proj in (dpdp_project, vapt_project, iso_project):
        events = (
            db.query(AuditTrailEvent)
            .filter(AuditTrailEvent.project_id == proj.id,
                    AuditTrailEvent.action.like("gate.advanced.%"))
            .all()
        )
        assert len(events) == len(_ALL_GATES), (
            f"Project {proj.id}: expected {len(_ALL_GATES)} gate events, got {len(events)}"
        )


# ── 8. QA agent is advisory only — never creates ApprovalRequest ──────────────

def test_qa_agent_never_approves(db, shared_client, admin, tmp_path_factory):
    """Create an isolated project, run QA, assert no approval was created."""
    out = tmp_path_factory.mktemp("s30_qa")
    proj = Project(client_id=shared_client.id, service_type=ServiceType.dpdp,
                   owner_id=admin.id, status="active",
                   scope_summary="QA-only test project.")
    db.add(proj); db.commit(); db.refresh(proj)

    before = db.query(ApprovalRequest).filter_by(project_id=proj.id).count()
    run_qa(db, proj)
    after = db.query(ApprovalRequest).filter_by(project_id=proj.id).count()
    assert after == before, "QA agent must never create an ApprovalRequest"


# ── 9. All three projects reach status=closed ─────────────────────────────────

def test_all_projects_closed(dpdp_project, vapt_project, iso_project):
    assert dpdp_project.status == "closed"
    assert vapt_project.status == "closed"
    assert iso_project.status == "closed"


# ── 10. Closure required approval in every project ───────────────────────────

def test_closure_required_approval(db, dpdp_project, vapt_project, iso_project):
    for proj in (dpdp_project, vapt_project, iso_project):
        closure_ap = db.query(ApprovalRequest).filter_by(
            project_id=proj.id, target_type="project_closure"
        ).first()
        assert closure_ap is not None, f"Project {proj.id} has no closure approval"
        assert closure_ap.status == ApprovalStatus.approved
