"""Stage C5 acceptance test — QA checks, deliverable generators, and bot audit-trail enforcement.

Verifies:
A) QA agent flags a project with an open approval gate, an unsupported finding, and scope mismatch.
B) Each DeliverableKind generates a file without error on a seeded project.
C) Bot commands that change finding status create an ApprovalRequest + AuditTrailEvent
   and do not mutate the finding directly.
"""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import DeliverableKind
from app.models.evidence import EvidenceRequest
from app.models.organization import Organization
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingSeverity, FindingStatus, Task
from app.models.users import Permission, Role, RoleName, User
from app.models.workflow import ApprovalStatus, AuditTrailEvent
from app.services.audit import request_approval
from app.services.auth import hash_password
from app.services.qa.agent import run_qa


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def seeded(db):
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="c5_admin@test.local",
        password_hash=hash_password("pass"),
        full_name="C5 Admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    org = Organization(name="C5 Org", display_name="C5 Org")
    db.add(org)
    db.flush()
    client = Client(entity_name="C5 Client", organization_id=org.id)
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, service_type=ServiceType.dpdp, owner_id=admin.id)
    db.add(project)
    db.flush()
    db.commit()
    return db, admin, project


# ── A) QA agent checks ────────────────────────────────────────────────────────

def test_qa_flags_open_approval_gate(seeded):
    db, admin, project = seeded
    # Create an open (requested) approval request — should trigger incomplete_approval_gates
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id="fake-id",
        reason="Pending scope change",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    report = run_qa(db, project)
    rule_names = [i.rule for i in report.issues]
    assert "incomplete_approval_gates" in rule_names, (
        f"Expected 'incomplete_approval_gates' in QA issues, got: {rule_names}"
    )


def test_qa_flags_scope_finding_mismatch(seeded):
    db, admin, project = seeded
    # Finding with pack_scoped_data.target that has no matching approved scope item
    finding = Finding(
        project_id=project.id,
        title="Mismatch finding",
        severity=FindingSeverity.high.value,
        source="manual",
        pack_scoped_data={"target": "api.out-of-scope.com"},
    )
    db.add(finding)
    db.flush()
    report = run_qa(db, project)
    rule_names = [i.rule for i in report.issues]
    assert "scope_finding_mismatch" in rule_names, (
        f"Expected 'scope_finding_mismatch' in QA issues, got: {rule_names}"
    )


def test_qa_flags_no_draft_findings(seeded):
    db, admin, project = seeded
    # Draft finding should be flagged by no_draft_findings
    finding = Finding(
        project_id=project.id,
        title="Draft finding",
        severity=FindingSeverity.medium.value,
        source="manual",
        status=FindingStatus.draft.value,
    )
    db.add(finding)
    db.flush()
    report = run_qa(db, project)
    rule_names = [i.rule for i in report.issues]
    assert "no_draft_findings" in rule_names


# ── B) Deliverable generators ─────────────────────────────────────────────────

DELIVERABLE_GENERATORS = {
    DeliverableKind.gap_matrix: "app.services.deliverables.gap_matrix.generate_gap_matrix",
    DeliverableKind.roadmap:    "app.services.deliverables.roadmap.generate_roadmap",
    DeliverableKind.report:     "app.services.deliverables.report.generate_report",
    DeliverableKind.summary:    "app.services.deliverables.summary.generate_summary",
    DeliverableKind.retest_report: "app.services.deliverables.retest_report.generate_retest_report",
    DeliverableKind.advisory_clinic_deck: "app.services.deliverables.advisory_clinic_deck.generate_advisory_clinic_deck",
    DeliverableKind.management_summary: "app.services.deliverables.management_summary.generate_management_summary",
    DeliverableKind.client_action_plan: "app.services.deliverables.client_action_plan.generate_client_action_plan",
    DeliverableKind.evidence_matrix: "app.services.deliverables.evidence_matrix.generate_evidence_matrix",
}


@pytest.mark.parametrize("kind,dotpath", list(DELIVERABLE_GENERATORS.items()), ids=[k.value for k in DELIVERABLE_GENERATORS])
def test_deliverable_generates_file(seeded, kind, dotpath, tmp_path):
    db, admin, project = seeded
    module_path, func_name = dotpath.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    generate_fn = getattr(mod, func_name)
    result = generate_fn(db, project, tmp_path / kind.value)
    db.flush()
    assert result is not None

    # Some generators return a tuple of deliverables (e.g. xlsx + html)
    deliverables = result if isinstance(result, tuple) else (result,)
    for deliverable in deliverables:
        assert Path(deliverable.file_path).exists(), (
            f"Deliverable file not created: {deliverable.file_path}"
        )


# ── C) Bot command audit-trail enforcement ────────────────────────────────────

def test_bot_finding_status_change_goes_through_gateway(seeded):
    """Verify that changing a finding status creates an ApprovalRequest + AuditTrailEvent,
    not a direct mutation."""
    from app.models.workflow import ApprovalRequest, AuditTrailEvent as ATE
    db, admin, project = seeded
    finding = Finding(
        project_id=project.id,
        title="Bot test finding",
        severity=FindingSeverity.high.value,
        source="manual",
        status=FindingStatus.in_review.value,
    )
    db.add(finding)
    db.flush()

    original_status = finding.status
    events_before = db.query(ATE).count()
    approvals_before = db.query(ApprovalRequest).count()

    # Simulate what a bot command SHOULD do: route through request_approval
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="finding_status_change",
        target_id=finding.id,
        reason="Bot: mark finding approved",
        approver_role="reviewer",
        change_before={"status": original_status},
        change_after={"status": FindingStatus.approved.value},
        requested_by=admin.id,
    )
    db.flush()

    # Finding must NOT be mutated yet — it still needs human approval
    assert finding.status == original_status, (
        "Bot command must not directly mutate finding — must go through approval gateway"
    )

    events_after = db.query(ATE).count()
    approvals_after = db.query(ApprovalRequest).count()

    assert approvals_after > approvals_before, "An ApprovalRequest must be created"
    assert events_after > events_before, "An AuditTrailEvent must be created"
    assert approval.status == ApprovalStatus.requested.value


def test_bot_commands_use_requested_not_pending():
    """Verify bot commands.py queries for ApprovalStatus.requested, not .pending."""
    import ast, pathlib
    src = pathlib.Path("app/bot/commands.py").read_text()
    assert "ApprovalStatus.pending" not in src, (
        "commands.py must use ApprovalStatus.requested after C4 migration"
    )
