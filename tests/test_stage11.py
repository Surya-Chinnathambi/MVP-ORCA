"""Stage 11 acceptance test — Web UI.

Verifies:
1. Each of the 14 pages returns 200 when authenticated.
2. Approval queue renders pending items.
3. Unauthenticated request redirects to /ui/login.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base, get_db
from app.main import app
from app.models.clients import Client, Project, ServiceType
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus
from app.models.users import Role, RoleName, User
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.auth import hash_password


# ── DB override ───────────────────────────────────────────────────────────────

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
def _seed(_engine):
    """Seed DB with admin user, client, project, scope, approval, finding."""
    Sess = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    with Session(_engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        admin = User(
            email="web_admin@test.local",
            password_hash=hash_password("password"),
            full_name="Web Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()

        client = Client(entity_name="Web Test Corp")
        db.add(client)
        db.flush()

        project = Project(
            client_id=client.id,
            service_type=ServiceType.dpdp,
            owner_id=admin.id,
            pack_id="dpdp",
            gates={},
        )
        db.add(project)
        db.flush()

        scope = ScopeItem(
            project_id=project.id, kind="asset", value="web-app.example.com", approved=False
        )
        db.add(scope)
        db.flush()

        approval = ApprovalRequest(
            project_id=project.id,
            target_type="scope_item",
            target_id=scope.id,
            reason="New asset in scope",
            approver_role="partner",
            status=ApprovalStatus.pending,
        )
        db.add(approval)
        db.flush()

        finding = Finding(
            project_id=project.id,
            title="XSS in login form",
            description="Reflected XSS found.",
            severity=FindingSeverity.high,
            status=FindingStatus.open,
            source=FindingSource.manual,
        )
        db.add(finding)
        db.commit()

        return {
            "admin_id": admin.id,
            "project_id": project.id,
            "client_id": client.id,
            "approval_id": approval.id,
        }


@pytest.fixture(scope="module")
def client(_engine, _seed):
    """TestClient with DB override, returns logged-in client."""
    def override_db():
        db = sessionmaker(bind=_engine, autocommit=False, autoflush=False)()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    tc = TestClient(app, base_url="http://testserver")

    # Login so session cookie is set for all subsequent requests
    resp = tc.post(
        "/ui/login",
        data={"email": "web_admin@test.local", "password": "password"},
        follow_redirects=True,
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"

    yield tc, _seed["project_id"]
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(tc, url):
    resp = tc.get(url, follow_redirects=True)
    return resp


# ── Page rendering tests ──────────────────────────────────────────────────────

def test_clients_page(client):
    tc, pid = client
    resp = get(tc, "/ui/clients")
    assert resp.status_code == 200
    assert "Web Test Corp" in resp.text


def test_project_dashboard(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}")
    assert resp.status_code == 200
    assert "Review Gates" in resp.text


def test_scope_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/scope")
    assert resp.status_code == 200
    assert "Scope Builder" in resp.text


def test_pack_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/pack")
    assert resp.status_code == 200
    assert "Methodology Pack" in resp.text


def test_evidence_requests_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/evidence-requests")
    assert resp.status_code == 200
    assert "Evidence Requests" in resp.text


def test_evidence_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/evidence")
    assert resp.status_code == 200
    assert "Evidence Review" in resp.text


def test_tasks_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/tasks")
    assert resp.status_code == 200
    assert "Task Board" in resp.text


def test_findings_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/findings")
    assert resp.status_code == 200
    assert "Findings Register" in resp.text
    assert "XSS in login form" in resp.text


def test_deliverables_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/deliverables")
    assert resp.status_code == 200
    assert "Report Builder" in resp.text


def test_remediation_page(client):
    tc, pid = client
    resp = get(tc, f"/ui/projects/{pid}/remediation")
    assert resp.status_code == 200
    assert "Remediation Tracker" in resp.text


def test_approvals_page(client):
    tc, pid = client
    resp = get(tc, "/ui/approvals")
    assert resp.status_code == 200
    assert "Approval Queue" in resp.text


def test_approvals_shows_pending(client):
    """Approval queue renders pending items."""
    tc, pid = client
    resp = get(tc, "/ui/approvals")
    assert resp.status_code == 200
    assert "pending" in resp.text
    assert "New asset in scope" in resp.text


def test_admin_users_page(client):
    tc, pid = client
    resp = get(tc, "/ui/admin/users")
    assert resp.status_code == 200
    assert "Users" in resp.text
    assert "web_admin@test.local" in resp.text


def test_login_page(client):
    tc, pid = client
    resp = get(tc, "/ui/login")
    # Already logged in → should redirect to /ui/clients
    assert resp.status_code == 200


# ── Unauthenticated redirect ──────────────────────────────────────────────────

def test_unauthenticated_redirects_to_login():
    """Fresh client (no session cookie) must redirect to /ui/login."""
    def override_db():
        # Need a minimal DB for this test too
        e = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(e)
        Sess = sessionmaker(bind=e, autocommit=False, autoflush=False)
        db = Sess()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        anon = TestClient(app, base_url="http://testserver")
        resp = anon.get("/ui/clients", follow_redirects=False)
        assert resp.status_code in (302, 307), f"Expected redirect, got {resp.status_code}"
        assert "/ui/login" in resp.headers.get("location", ""), resp.headers
    finally:
        app.dependency_overrides.clear()
