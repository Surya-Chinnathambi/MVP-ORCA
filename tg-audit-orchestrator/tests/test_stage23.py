"""Stage 23 acceptance test — AI agent layer (advisory only).

Verifies:
1. classify_evidence_agent labels a fixture evidence item (mocked Claude API).
2. Draft is status=draft; suggested_classification is one of the known categories.
3. draft_finding_agent produces a draft with status=draft and severity_confirmed=False.
4. agent_decide_approval raises AgentGuardError — agents cannot approve.
5. agent_set_severity raises AgentGuardError — agents cannot confirm severity.
6. agent_release_report raises AgentGuardError.
7. Every agent action writes an AuditTrailEvent with actor_type=agent.
8. Restricted-evidence classification raises AgentGuardError for users without permission.
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.agent import AgentDraft, AgentType, DraftStatus
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceItem, ReviewerStatus
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.models.workflow import AuditTrailEvent
from app.services.auth import hash_password
from app.services.agents.base import (
    AgentGuardError,
    agent_decide_approval,
    agent_release_report,
    agent_set_severity,
)


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def db(engine):
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Sess()
    for name in [r.value for r in RoleName]:
        session.add(Role(name=name))
    admin = User(
        email="s23_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage23 Admin",
        is_active=True,
    )
    analyst = User(
        email="s23_analyst@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage23 Analyst",
        is_active=True,
    )
    session.add_all([admin, analyst])
    session.commit()
    session.refresh(admin)
    session.refresh(analyst)
    yield session, admin.id, analyst.id
    session.close()


@pytest.fixture(scope="module")
def project_fixture(db):
    session, admin_id, _ = db
    org = Organization(name="S23 Org")
    session.add(org)
    session.flush()
    client = Client(entity_name="S23 Client", organization_id=org.id)
    session.add(client)
    session.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        owner_id=admin_id,
        status="active",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


def _make_evidence(session, project_id, *, text="Policy document text", restricted=False):
    item = EvidenceItem(
        project_id=project_id,
        source_file="doc.txt",
        sha256="c" * 64,
        mime="text/plain",
        reviewer_status=ReviewerStatus.accepted.value,
        extracted_text=text,
        is_restricted=restricted,
    )
    session.add(item)
    session.flush()
    return item


# ── Guardrail tests ───────────────────────────────────────────────────────────

def test_agent_cannot_approve():
    """agent_decide_approval must always raise AgentGuardError."""
    with pytest.raises(AgentGuardError, match="cannot approve"):
        agent_decide_approval()


def test_agent_cannot_set_severity():
    """agent_set_severity must always raise AgentGuardError."""
    with pytest.raises(AgentGuardError, match="cannot set or confirm"):
        agent_set_severity()


def test_agent_cannot_release_report():
    """agent_release_report must always raise AgentGuardError."""
    with pytest.raises(AgentGuardError, match="cannot release"):
        agent_release_report()


# ── Classification agent ──────────────────────────────────────────────────────

def test_classify_evidence_agent_returns_draft(db, project_fixture):
    """classify_evidence_agent returns an AgentDraft with status=draft."""
    session, admin_id, analyst_id = db
    item = _make_evidence(session, project_fixture.id, text="Access control policy review")
    session.commit()

    with patch("app.services.agents.classify.call_claude", return_value="access_control"):
        from app.services.agents.classify import classify_evidence_agent
        draft = classify_evidence_agent(session, item.id, analyst_id)
        session.commit()

    assert isinstance(draft, AgentDraft)
    assert draft.status == DraftStatus.draft.value
    assert draft.agent_type == AgentType.classify_evidence.value
    assert draft.payload["suggested_classification"] == "access_control"
    assert draft.payload["actor_type"] == "agent"
    assert draft.requested_by == analyst_id


def test_classify_evidence_normalises_unrecognised_label(db, project_fixture):
    """An unrecognised Claude response falls back to 'other'."""
    session, admin_id, analyst_id = db
    item = _make_evidence(session, project_fixture.id)
    session.commit()

    with patch("app.services.agents.classify.call_claude", return_value="something_weird"):
        from app.services.agents.classify import classify_evidence_agent
        draft = classify_evidence_agent(session, item.id, analyst_id)
        session.commit()

    assert draft.payload["suggested_classification"] == "other"


def test_classify_restricted_evidence_blocked_without_permission(db, project_fixture):
    """classify_evidence_agent raises AgentGuardError for restricted evidence without permission."""
    session, admin_id, analyst_id = db
    item = _make_evidence(session, project_fixture.id, restricted=True)
    session.commit()

    with patch("app.services.agents.classify.call_claude", return_value="encryption"):
        from app.services.agents.classify import classify_evidence_agent
        with pytest.raises(AgentGuardError, match="restricted evidence"):
            classify_evidence_agent(session, item.id, analyst_id)

    session.rollback()


# ── Draft-finding agent ───────────────────────────────────────────────────────

def test_draft_finding_agent_status_draft_no_severity_confirmed(db, project_fixture):
    """draft_finding_agent produces status=draft with severity_confirmed=False."""
    session, admin_id, analyst_id = db

    mock_response = '{"title": "Weak Access Controls", "description": "MFA not enforced.", "suggested_severity": "high", "rationale": "Users bypass MFA."}'

    with patch("app.services.agents.draft_finding.call_claude", return_value=mock_response):
        from app.services.agents.draft_finding import draft_finding_agent
        draft = draft_finding_agent(
            session,
            project_fixture.id,
            "Weak Access Controls",
            "MFA is not enforced for privileged accounts.",
            analyst_id,
        )
        session.commit()

    assert draft.status == DraftStatus.draft.value
    assert draft.payload["status"] == "draft"
    assert draft.payload["severity_confirmed"] is False
    # suggested_severity is present but advisory only
    assert "suggested_severity" in draft.payload
    # No Finding was created — the draft is purely advisory
    from app.models.tasks import Finding
    findings_count = session.query(Finding).filter_by(project_id=project_fixture.id).count()
    assert findings_count == 0, "Agent must not create a Finding row"


def test_draft_finding_agent_logs_audit_event(db, project_fixture):
    """draft_finding_agent writes an AuditTrailEvent with actor_type=agent."""
    session, admin_id, analyst_id = db

    mock_response = '{"title": "SQL Injection", "description": "Input not sanitised.", "suggested_severity": "critical", "rationale": "Data at risk."}'

    before = session.query(AuditTrailEvent).count()

    with patch("app.services.agents.draft_finding.call_claude", return_value=mock_response):
        from app.services.agents.draft_finding import draft_finding_agent
        draft_finding_agent(
            session, project_fixture.id, "SQL Injection", "Unsanitised input found.", analyst_id
        )
        session.commit()

    after = session.query(AuditTrailEvent).count()
    assert after > before

    latest = (
        session.query(AuditTrailEvent)
        .order_by(AuditTrailEvent.ts.desc())
        .first()
    )
    assert latest.after.get("actor_type") == "agent"
    assert latest.actor_id is None, "agent events must have actor_id=None"


# ── Classification agent also logs ───────────────────────────────────────────

def test_classify_evidence_logs_actor_type_agent(db, project_fixture):
    """classify_evidence_agent audit event carries actor_type=agent."""
    session, admin_id, analyst_id = db
    item = _make_evidence(session, project_fixture.id, text="Network firewall config review")
    session.commit()

    before = session.query(AuditTrailEvent).count()

    with patch("app.services.agents.classify.call_claude", return_value="network_security"):
        from app.services.agents.classify import classify_evidence_agent
        classify_evidence_agent(session, item.id, analyst_id)
        session.commit()

    after = session.query(AuditTrailEvent).count()
    assert after > before

    latest = (
        session.query(AuditTrailEvent)
        .filter_by(action="agent.classify_evidence")
        .order_by(AuditTrailEvent.ts.desc())
        .first()
    )
    assert latest is not None
    assert latest.after.get("actor_type") == "agent"
    assert latest.actor_id is None
