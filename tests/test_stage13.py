"""Stage 13 acceptance test — Pilot dry run + MVP acceptance.

Verifies both the DPDP and VAPT pilots complete the full chain:
  client/project setup → scope → pack selection → plan generation →
  evidence ingestion + mapping → task tracking → findings →
  human approval gates (all 7) → QA review → deliverables → closure

Each pilot must:
  - Have a complete audit trail (events for every controlled change)
  - Have all 7 gates passed
  - Have at least one finding with evidence
  - Have all approval requests decided (none left pending)
  - Have the project in 'closed' status
  - Have at least one deliverable of each kind (gap_matrix, roadmap, report)
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
from app.models.delivery import Deliverable, DeliverableKind, RemediationAction
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
from ptorc_adapter.importer import run_import

_ALL_GATES = [
    "G1_scope", "G2_evidence_requests", "G3_evidence_complete",
    "G4_findings", "G5_qa", "G6_report", "G7_closure",
]


# ── Shared DB fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def _db(_engine):
    Sess = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    db = Sess()
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="pilot_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Pilot Admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    yield db, admin.id
    db.close()


# ── Helper: PT-Orc fixture run dir ───────────────────────────────────────────

def _make_ptorc_run_dir(tmp_path: Path, project_id: str) -> Path:
    run_dir = tmp_path / "ptorc_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "scope.json").write_text(json.dumps({
        "project_ref": project_id,
        "engagement_profile": "external",
        "testing_depth": "standard",
        "auth_level": "none",
        "targets": ["target.test.local"],
        "rules_of_engagement": "No DoS",
        "window": {"start": "2026-06-01", "end": "2026-06-14"},
    }), encoding="utf-8")

    evidence_lines = [
        json.dumps({"id": "ev-001", "phase": "01_dns",
                    "source_file": "dns.txt", "sha256": "a" * 64,
                    "summary": "DNS records"}),
        json.dumps({"id": "ev-002", "phase": "04_tls",
                    "source_file": "tls.txt", "sha256": "b" * 64,
                    "summary": "TLS 1.0 enabled"}),
    ]
    (run_dir / "evidence_manifest.jsonl").write_text(
        "\n".join(evidence_lines), encoding="utf-8"
    )

    findings_lines = [
        json.dumps({"id": "f-001", "title": "TLS 1.0 enabled",
                    "severity": "medium", "phase": "04_tls",
                    "evidence_ids": ["ev-002"],
                    "description": "TLS 1.0 deprecated.",
                    "recommendation": "Disable TLS 1.0."}),
        json.dumps({"id": "f-002", "title": "Exposed .git directory",
                    "severity": "high", "phase": "05_web",
                    "evidence_ids": ["ev-001"],
                    "description": "Source code leak.",
                    "recommendation": "Block .git access."}),
    ]
    (run_dir / "findings.jsonl").write_text(
        "\n".join(findings_lines), encoding="utf-8"
    )

    (run_dir / "report_bundle.json").write_text(json.dumps({
        "project_ref": project_id,
        "profile": "external",
        "retest_status": "scheduled",
        "residual_risk": "Medium",
        "counts": {"findings": 2, "evidence": 2},
    }), encoding="utf-8")

    return run_dir


# ── Pilot runner helpers ──────────────────────────────────────────────────────

def _advance_gate(db: Session, project: Project, gate: str, actor_id: str) -> None:
    gates = dict(project.gates or {})
    gates[gate] = True
    project.gates = gates
    record_event(
        db, action=f"gate.advanced.{gate}", target_type="project",
        target_id=project.id, actor_id=actor_id, project_id=project.id,
        before={gate: False}, after={gate: True},
    )


def _approve(db: Session, *, project_id: str, target_type: str, target_id: str,
             reason: str, actor_id: str) -> ApprovalRequest:
    ap = request_approval(
        db, project_id=project_id, target_type=target_type, target_id=target_id,
        reason=reason, approver_role="partner", requested_by=actor_id,
    )
    db.commit()
    decide_approval(db, approval_id=ap.id, approved=True, decider_id=actor_id)
    db.commit()
    return ap


# ── DPDP pilot ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _dpdp_run(_db, tmp_path_factory):
    db, admin_id = _db
    tmp = tmp_path_factory.mktemp("dpdp")

    # Client + project
    client = Client(name="Pilot DPDP Corp", sector="fintech")
    db.add(client)
    db.flush()
    project = Project(
        client_id=client.id, service_type=ServiceType.dpdp,
        owner_id=admin_id, status="setup",
        scope_summary="DPDP readiness pilot",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pid = project.id

    # Scope + G1
    si = ScopeItem(project_id=pid, kind=ScopeItemKind.business_unit.value,
                   value="Customer data processing", approved=False)
    db.add(si)
    db.flush()
    _approve(db, project_id=pid, target_type="scope", target_id=si.id,
             reason="Scope approval", actor_id=admin_id)
    si.approved = True
    db.commit()
    _advance_gate(db, project, "G1_scope", admin_id)
    db.commit()

    # Pack + plan
    pack = load_pack("dpdp")
    project.pack_id = pack.key
    db.commit()
    generate_plan(db, project, pack)
    db.commit()

    # Evidence requests received + G2
    for er in db.query(EvidenceRequest).filter_by(project_id=pid).all():
        er.status = EvidenceRequestStatus.received
    db.commit()
    _advance_gate(db, project, "G2_evidence_requests", admin_id)
    db.commit()

    # Ingest evidence + G3
    ev = ingest_file(db, project_id=pid,
                     data=b"Privacy Notice v1.0 - personal data processing",
                     filename="privacy_notice.txt")
    ev.reviewer_status = "accepted"
    db.commit()
    _advance_gate(db, project, "G3_evidence_complete", admin_id)
    db.commit()

    # Finding + severity approval + G4
    finding = Finding(
        project_id=pid,
        title="Missing grievance officer in privacy notice",
        description="DPDP Act §13 requires a listed grievance officer.",
        severity=FindingSeverity.high,
        status=FindingStatus.in_review,
        source=FindingSource.manual,
        owner_id=admin_id,
        evidence_item_ids=[ev.id],
    )
    db.add(finding)
    db.flush()
    _approve(db, project_id=pid, target_type="finding_severity",
             target_id=finding.id, reason="Severity confirmed HIGH", actor_id=admin_id)
    finding.status = FindingStatus.approved
    db.add(RemediationAction(finding_id=finding.id, project_id=pid,
                             action="Add grievance officer details",
                             owner_id=admin_id, status="open", residual_risk="low"))
    db.commit()
    _advance_gate(db, project, "G4_findings", admin_id)
    db.commit()

    # QA + G5
    db.refresh(project)
    run_qa(db, project)
    _advance_gate(db, project, "G5_qa", admin_id)
    db.commit()

    # Deliverables
    out = tmp / "deliverables"
    out.mkdir()
    db.refresh(project)
    generate_gap_matrix(db, project, out)
    generate_roadmap(db, project, out)
    report_del = generate_report(db, project, out)
    db.commit()

    _approve(db, project_id=pid, target_type="deliverable",
             target_id=report_del.id, reason="Report approved", actor_id=admin_id)
    _advance_gate(db, project, "G6_report", admin_id)
    db.commit()

    # Closure + G7
    _approve(db, project_id=pid, target_type="project_closure",
             target_id=pid, reason="Close with residual risk: low", actor_id=admin_id)
    project.status = "closed"
    db.commit()
    _advance_gate(db, project, "G7_closure", admin_id)
    db.commit()
    db.refresh(project)

    return {"project_id": pid, "admin_id": admin_id}


# ── VAPT pilot ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _vapt_run(_db, tmp_path_factory):
    db, admin_id = _db
    tmp = tmp_path_factory.mktemp("vapt")

    # Client + project
    client = Client(name="Pilot VAPT Corp", sector="ecommerce")
    db.add(client)
    db.flush()
    project = Project(
        client_id=client.id, service_type=ServiceType.vapt,
        owner_id=admin_id, status="setup",
        scope_summary="External VAPT pilot",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pid = project.id

    # Scope + G1
    si = ScopeItem(project_id=pid, kind=ScopeItemKind.asset.value,
                   value="target.test.local", approved=False)
    db.add(si)
    db.flush()
    _approve(db, project_id=pid, target_type="scope", target_id=si.id,
             reason="VAPT scope approval", actor_id=admin_id)
    si.approved = True
    db.commit()
    _advance_gate(db, project, "G1_scope", admin_id)
    db.commit()

    # Pack + plan
    pack = load_pack("vapt")
    project.pack_id = pack.key
    db.commit()
    generate_plan(db, project, pack)
    db.commit()

    # PT-Orc import (fixture run dir) — result fields are string IDs
    run_dir = _make_ptorc_run_dir(tmp, pid)
    result = run_import(db, pid, run_dir)

    # Decide the approvals that _import_scope already created (result.scope_approvals)
    # and mark the scope items approved.
    for ap_id in result.scope_approvals:
        decide_approval(db, approval_id=ap_id, approved=True, decider_id=admin_id)
    for si_id in result.scope_items:
        si_obj = db.get(ScopeItem, si_id)
        if si_obj:
            si_obj.approved = True
    db.commit()

    # Evidence requests received + accept items + G2 + G3
    for er in db.query(EvidenceRequest).filter_by(project_id=pid).all():
        er.status = EvidenceRequestStatus.received
    for ei in db.query(EvidenceItem).filter_by(project_id=pid).all():
        ei.reviewer_status = "accepted"
    db.commit()
    _advance_gate(db, project, "G2_evidence_requests", admin_id)
    _advance_gate(db, project, "G3_evidence_complete", admin_id)
    db.commit()

    # Approve all findings + add remediations + G4
    # result.findings is a list of string IDs; look up objects to mutate
    for finding in db.query(Finding).filter_by(project_id=pid).all():
        _approve(db, project_id=pid, target_type="finding_severity",
                 target_id=finding.id, reason="Severity confirmed",
                 actor_id=admin_id)
        finding.status = FindingStatus.approved
        db.add(RemediationAction(finding_id=finding.id, project_id=pid,
                                 action=f"Remediate: {finding.title}",
                                 owner_id=admin_id, status="open", residual_risk="low"))
    db.commit()
    _advance_gate(db, project, "G4_findings", admin_id)
    db.commit()

    # QA + G5
    db.refresh(project)
    run_qa(db, project)
    _advance_gate(db, project, "G5_qa", admin_id)
    db.commit()

    # Deliverables + G6
    out = tmp / "deliverables"
    out.mkdir()
    db.refresh(project)
    generate_gap_matrix(db, project, out)
    generate_roadmap(db, project, out)
    report_del = generate_report(db, project, out)
    db.commit()
    _approve(db, project_id=pid, target_type="deliverable",
             target_id=report_del.id, reason="Report approved", actor_id=admin_id)
    _advance_gate(db, project, "G6_report", admin_id)
    db.commit()

    # Closure + G7
    _approve(db, project_id=pid, target_type="project_closure",
             target_id=pid, reason="Close VAPT engagement", actor_id=admin_id)
    project.status = "closed"
    db.commit()
    _advance_gate(db, project, "G7_closure", admin_id)
    db.commit()
    db.refresh(project)

    return {
        "project_id": pid,
        "admin_id": admin_id,
        "ptorc_finding_ids": result.findings,
        "ptorc_evidence_ids": result.evidence_items,
    }


# ── Assertion helpers ─────────────────────────────────────────────────────────

def _assert_full_chain(db: Session, project_id: str) -> None:
    project = db.get(Project, project_id)

    # All 7 gates passed
    gates = project.gates or {}
    for gate in _ALL_GATES:
        assert gates.get(gate), f"Gate {gate} not passed for project {project_id}"

    # Project closed
    assert project.status == "closed", f"Expected 'closed', got {project.status!r}"

    # At least one finding with evidence
    findings = db.query(Finding).filter_by(project_id=project_id).all()
    assert findings, "No findings recorded"
    findings_with_evidence = [f for f in findings if f.evidence_item_ids]
    assert findings_with_evidence, "No findings have evidence item links"

    # No pending approvals (all decided)
    pending = (
        db.query(ApprovalRequest)
        .filter_by(project_id=project_id, status=ApprovalStatus.pending)
        .count()
    )
    assert pending == 0, f"{pending} approval(s) still pending for project {project_id}"

    # Audit trail has events
    events = db.query(AuditTrailEvent).filter_by(project_id=project_id).all()
    assert len(events) >= 7, f"Expected ≥7 audit events, got {len(events)}"

    # All three deliverable kinds present
    for kind in (DeliverableKind.gap_matrix, DeliverableKind.roadmap, DeliverableKind.report):
        d = db.query(Deliverable).filter_by(project_id=project_id, kind=kind).first()
        assert d is not None, f"Missing deliverable kind: {kind.value}"
        assert Path(d.file_path).exists(), f"Deliverable file missing: {d.file_path}"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDPDPPilot:
    def test_all_gates_passed(self, _dpdp_run, _db):
        db, _ = _db
        project_id = _dpdp_run["project_id"]
        project = db.get(Project, project_id)
        gates = project.gates or {}
        for gate in _ALL_GATES:
            assert gates.get(gate), f"DPDP gate {gate} not passed"

    def test_project_closed(self, _dpdp_run, _db):
        db, _ = _db
        project = db.get(Project, _dpdp_run["project_id"])
        assert project.status == "closed"

    def test_findings_have_evidence(self, _dpdp_run, _db):
        db, _ = _db
        findings = db.query(Finding).filter_by(project_id=_dpdp_run["project_id"]).all()
        assert any(f.evidence_item_ids for f in findings), "No finding has evidence links"

    def test_no_pending_approvals(self, _dpdp_run, _db):
        db, _ = _db
        pending = (
            db.query(ApprovalRequest)
            .filter_by(project_id=_dpdp_run["project_id"], status=ApprovalStatus.pending)
            .count()
        )
        assert pending == 0

    def test_audit_trail_complete(self, _dpdp_run, _db):
        db, _ = _db
        events = db.query(AuditTrailEvent).filter_by(
            project_id=_dpdp_run["project_id"]
        ).all()
        assert len(events) >= 7
        gate_events = [e for e in events if e.action.startswith("gate.advanced.")]
        assert len(gate_events) == 7, f"Expected 7 gate events, got {len(gate_events)}"

    def test_deliverables_generated(self, _dpdp_run, _db):
        db, _ = _db
        pid = _dpdp_run["project_id"]
        for kind in (DeliverableKind.gap_matrix, DeliverableKind.roadmap, DeliverableKind.report):
            d = db.query(Deliverable).filter_by(project_id=pid, kind=kind).first()
            assert d is not None, f"Missing deliverable: {kind.value}"
            assert Path(d.file_path).exists()

    def test_full_chain(self, _dpdp_run, _db):
        db, _ = _db
        _assert_full_chain(db, _dpdp_run["project_id"])


class TestVAPTPilot:
    def test_ptorc_findings_imported_as_in_review(self, _vapt_run, _db):
        """PT-Orc findings must arrive as source=ptorc; they must not be auto-approved."""
        db, _ = _db
        finding_ids = _vapt_run["ptorc_finding_ids"]
        assert finding_ids, "No findings imported from PT-Orc fixture"
        for fid in finding_ids:
            f = db.get(Finding, fid)
            assert f is not None, f"Finding {fid} not found in DB"
            assert f.source == FindingSource.ptorc.value, (
                f"Finding {fid} source should be 'ptorc', got {f.source!r}"
            )

    def test_ptorc_evidence_imported(self, _vapt_run, _db):
        evidence_ids = _vapt_run["ptorc_evidence_ids"]
        assert len(evidence_ids) >= 2

    def test_all_gates_passed(self, _vapt_run, _db):
        db, _ = _db
        project = db.get(Project, _vapt_run["project_id"])
        gates = project.gates or {}
        for gate in _ALL_GATES:
            assert gates.get(gate), f"VAPT gate {gate} not passed"

    def test_project_closed(self, _vapt_run, _db):
        db, _ = _db
        project = db.get(Project, _vapt_run["project_id"])
        assert project.status == "closed"

    def test_no_pending_approvals(self, _vapt_run, _db):
        db, _ = _db
        pending = (
            db.query(ApprovalRequest)
            .filter_by(project_id=_vapt_run["project_id"], status=ApprovalStatus.pending)
            .count()
        )
        assert pending == 0

    def test_audit_trail_complete(self, _vapt_run, _db):
        db, _ = _db
        events = db.query(AuditTrailEvent).filter_by(
            project_id=_vapt_run["project_id"]
        ).all()
        assert len(events) >= 7
        gate_events = [e for e in events if e.action.startswith("gate.advanced.")]
        assert len(gate_events) == 7

    def test_deliverables_generated(self, _vapt_run, _db):
        db, _ = _db
        pid = _vapt_run["project_id"]
        for kind in (DeliverableKind.gap_matrix, DeliverableKind.roadmap, DeliverableKind.report):
            d = db.query(Deliverable).filter_by(project_id=pid, kind=kind).first()
            assert d is not None, f"Missing deliverable: {kind.value}"
            assert Path(d.file_path).exists()

    def test_full_chain(self, _vapt_run, _db):
        db, _ = _db
        _assert_full_chain(db, _vapt_run["project_id"])
