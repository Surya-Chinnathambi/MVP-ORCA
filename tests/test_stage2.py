"""Stage 2 acceptance test — auth, RBAC, audit/approval gateway."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app as fastapi_app
from app.services.audit import decide_approval, record_event, request_approval
from app.services.auth import hash_password

import app.models  # noqa: F401
from app.models.users import Role, RoleName, User, Permission
from app.models.clients import Client, Project, ServiceType
from app.models.workflow import ApprovalStatus, AuditTrailEvent

# ── Test DB setup ────────────────────────────────────────────────────────────

TEST_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def engine():
    # StaticPool: all sessions share one connection → same in-memory DB
    e = create_engine(
        TEST_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def SessionTest(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def seeded_db(engine, SessionTest):
    """Seed 8 roles + admin user into the test DB."""
    with Session(engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        db.flush()
        admin_role = db.query(Role).filter_by(name=RoleName.admin).first()
        admin = User(
            email="admin@test.local",
            password_hash=hash_password("admin123"),
            full_name="Test Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))
        db.commit()
        yield db


@pytest.fixture(scope="module")
def client(seeded_db, SessionTest):
    def override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Helpers ──────────────────────────────────────────────────────────────────

def admin_session(client):
    """Return a new TestClient session already logged in as admin."""
    resp = client.post("/auth/login", json={"email": "admin@test.local", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_login_success(client):
    resp = client.post("/auth/login", json={"email": "admin@test.local", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.local"


def test_login_wrong_password(client):
    resp = client.post("/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert resp.status_code == 401


def test_me_unauthenticated(client):
    # fresh client with no session
    with TestClient(fastapi_app) as fresh:
        resp = fresh.get("/auth/me")
    assert resp.status_code == 401


def test_me_authenticated(client):
    admin_session(client)
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.local"


def test_create_user_as_admin(client):
    admin_session(client)
    resp = client.post("/users/", json={
        "email": "analyst@test.local",
        "full_name": "Anna Lyst",
        "password": "pass123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "analyst@test.local"
    assert "password" not in data
    assert "password_hash" not in data


def test_create_user_duplicate_email(client):
    admin_session(client)
    client.post("/users/", json={"email": "dup@test.local", "full_name": "D", "password": "x"})
    resp = client.post("/users/", json={"email": "dup@test.local", "full_name": "D2", "password": "x"})
    assert resp.status_code == 409


def test_unauthorized_user_gets_403(client, SessionTest):
    # Create a plain user with no permissions
    with SessionTest() as db:
        plain = User(
            email="noperm@test.local",
            password_hash=hash_password("pw"),
            full_name="No Perm",
            is_active=True,
        )
        db.add(plain)
        db.commit()

    def _noperm_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _noperm_db
    with TestClient(fastapi_app) as fresh:
        login_r = fresh.post("/auth/login", json={"email": "noperm@test.local", "password": "pw"})
        assert login_r.status_code == 200, login_r.text
        resp = fresh.get("/users/")
        assert resp.status_code == 403
    # Restore the module-scoped override so subsequent tests work
    def _restore():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()
    fastapi_app.dependency_overrides[get_db] = _restore


def test_assign_project_role(client, SessionTest):
    admin_session(client)
    # Get analyst user and analyst role IDs
    with SessionTest() as db:
        analyst_user = db.query(User).filter_by(email="analyst@test.local").first()
        analyst_role = db.query(Role).filter_by(name=RoleName.analyst).first()

    resp = client.post("/permissions/", json={
        "user_id": analyst_user.id,
        "role_id": analyst_role.id,
        "scope_level": "project",
        "scope_id": None,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == analyst_user.id
    assert data["scope_level"] == "project"


def test_list_roles(client):
    admin_session(client)
    resp = client.get("/roles/")
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert set(names) == {r.value for r in RoleName}


def test_approval_gateway(SessionTest):
    """Approval request created pending → decided approved → audit event written."""
    with SessionTest() as db:
        # Need a project for context
        client_row = Client(name="GW Test Corp")
        db.add(client_row)
        db.flush()
        project = Project(client_id=client_row.id, service_type=ServiceType.dpdp)
        db.add(project)
        db.flush()
        actor = db.query(User).filter_by(email="admin@test.local").first()

        # Create an approval request
        approval = request_approval(
            db,
            project_id=project.id,
            target_type="scope_item",
            target_id="fake-scope-id",
            reason="Added exclusion for PCI-DSS scope",
            approver_role=RoleName.reviewer.value,
            change_before={"approved": False},
            change_after={"approved": True},
            requested_by=actor.id,
        )
        db.flush()
        assert approval.status == ApprovalStatus.pending

        # Decide it approved
        resolved = decide_approval(
            db,
            approval_id=approval.id,
            approved=True,
            decider_id=actor.id,
            reason="Scope reviewed and accepted",
        )
        db.commit()

        assert resolved.status == ApprovalStatus.approved
        assert resolved.decided_by == actor.id
        assert resolved.decided_at is not None

        # Verify audit events were written (one for request, one for decision)
        events = db.query(AuditTrailEvent).filter_by(project_id=project.id).all()
        actions = [e.action for e in events]
        assert any("approval.requested" in a for a in actions)
        assert any("approval.approved" in a for a in actions)


def test_record_event_standalone(SessionTest):
    with SessionTest() as db:
        client_row = Client(name="Event Test Corp")
        db.add(client_row)
        db.flush()
        project = Project(client_id=client_row.id, service_type=ServiceType.vapt)
        db.add(project)
        db.flush()

        event = record_event(
            db,
            action="finding.created",
            target_type="finding",
            target_id="fake-finding-id",
            project_id=project.id,
            after={"severity": "high"},
        )
        db.commit()

        e = db.get(AuditTrailEvent, event.id)
        assert e.action == "finding.created"
        assert e.after == {"severity": "high"}
        assert e.ts is not None
