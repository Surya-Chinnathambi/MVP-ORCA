"""Stage 1 acceptance test — Client → Project → ScopeItem FK chain + timestamps."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
import app.models  # noqa: F401 — register all models
from app.models.clients import Client, Project, ServiceType
from app.models.scope import ScopeItem, ScopeItemKind, Framework, FrameworkKey, Requirement
from app.models.users import User, Role, RoleName, Permission, ScopeLevel
from app.models.evidence import EvidenceRequest, EvidenceItem, EvidenceRequestStatus, ReviewerStatus
from app.models.tasks import Task, Finding, TaskKind, FindingSeverity, FindingStatus, FindingSource
from app.models.workflow import ApprovalRequest, AuditTrailEvent, ApprovalStatus
from app.models.delivery import AdvisoryClinic, Deliverable, RemediationAction, DeliverableKind


@pytest.fixture(scope="module")
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_all_17_tables_created(db):
    """Original 17 MVP tables plus Stage 14 org/engagement tables all exist."""
    expected = {
        "users", "roles", "permissions",
        "clients", "projects",
        "scope_items", "frameworks", "requirements",
        "evidence_requests", "evidence_items",
        "tasks", "findings",
        "approval_requests", "audit_trail_events",
        "advisory_clinics", "deliverables", "remediation_actions",
        # Stage 14 additions
        "organizations", "engagement_states", "engagement_objectives",
    }
    actual = set(Base.metadata.tables.keys())
    assert expected <= actual, f"Missing tables: {expected - actual}"


def test_client_project_scopeitem_chain(db):
    """Create Client → Project → ScopeItem and verify FK chain + timestamps."""
    client = Client(entity_name="Acme Corp", sector="finance")
    db.add(client)
    db.flush()

    project = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        status="setup",
    )
    db.add(project)
    db.flush()

    scope_item = ScopeItem(
        project_id=project.id,
        kind=ScopeItemKind.inclusion,
        value="HR payroll data",
    )
    db.add(scope_item)
    db.commit()

    # Query back and verify
    c = db.get(Client, client.id)
    assert c is not None
    assert c.entity_name == "Acme Corp"
    assert c.created_at is not None

    p = db.get(Project, project.id)
    assert p is not None
    assert p.client_id == client.id
    assert p.service_type == ServiceType.dpdp
    assert p.created_at is not None

    s = db.get(ScopeItem, scope_item.id)
    assert s is not None
    assert s.project_id == project.id
    assert s.approved is False
    assert s.created_at is not None


def test_user_role_permission(db):
    role = Role(name=RoleName.analyst)
    db.add(role)
    db.flush()

    user = User(email="analyst@test.com", password_hash="x", full_name="Ana Lyst")
    db.add(user)
    db.flush()

    perm = Permission(
        user_id=user.id,
        scope_level=ScopeLevel.project,
        role_id=role.id,
    )
    db.add(perm)
    db.commit()

    queried = db.get(Permission, perm.id)
    assert queried.user_id == user.id
    assert queried.role_id == role.id
    assert queried.created_at is not None


def test_framework_requirement(db):
    fw = Framework(key=FrameworkKey.dpdp_act, title="DPDP Act 2023", version="1.0")
    db.add(fw)
    db.flush()

    # Reuse the project from previous test (create a fresh one)
    client = Client(entity_name="Beta Ltd")
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, service_type=ServiceType.dpdp)
    db.add(project)
    db.flush()

    req = Requirement(
        framework_id=fw.id,
        project_id=project.id,
        ref_code="DPDP-NOTICE-01",
        text="Privacy notice at collection",
        category="notice",
    )
    db.add(req)
    db.commit()

    r = db.get(Requirement, req.id)
    assert r.framework_id == fw.id
    assert r.project_id == project.id
    assert r.ref_code == "DPDP-NOTICE-01"


def test_finding_and_approval_workflow(db):
    client = Client(entity_name="Gamma Inc")
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, service_type=ServiceType.vapt)
    db.add(project)
    db.flush()

    finding = Finding(
        project_id=project.id,
        title="TLS 1.0 enabled",
        severity=FindingSeverity.high,
        status=FindingStatus.open,
        source=FindingSource.ptorc,
    )
    db.add(finding)
    db.flush()

    approval = ApprovalRequest(
        project_id=project.id,
        target_type="finding",
        target_id=finding.id,
        reason="Severity change from high to critical",
        approver_role="reviewer",
        status=ApprovalStatus.pending,
    )
    db.add(approval)
    db.flush()

    event = AuditTrailEvent(
        project_id=project.id,
        action="finding.severity_change_requested",
        target_type="finding",
        target_id=finding.id,
        before={"severity": "high"},
        after={"severity": "critical"},
    )
    db.add(event)
    db.commit()

    a = db.get(ApprovalRequest, approval.id)
    assert a.status == ApprovalStatus.pending
    assert a.project_id == project.id

    e = db.get(AuditTrailEvent, event.id)
    assert e.action == "finding.severity_change_requested"
    assert e.ts is not None
