"""Stage 3 acceptance test — clients, projects, scope builder with Gate 1."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app as fastapi_app
from app.services.auth import hash_password

import app.models  # noqa: F401
from app.models.users import Role, RoleName, User, Permission
from app.models.scope import ScopeItem
from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent

# ── Test DB ──────────────────────────────────────────────────────────────────

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
def SessionTest(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def seeded_db(engine, SessionTest):
    with Session(engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        db.flush()
        admin_role = db.query(Role).filter_by(name=RoleName.admin).first()
        admin = User(
            email="admin@stage3.local",
            password_hash=hash_password("admin123"),
            full_name="Stage3 Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))
        db.commit()
        yield db


@pytest.fixture(scope="module")
def client(seeded_db, SessionTest):
    def override():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app) as c:
        c.post("/auth/login", json={"email": "admin@stage3.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_create_client(client):
    resp = client.post("/clients/", json={
        "name": "Acme Finance",
        "sector": "banking",
        "contacts": [{"name": "Priya", "email": "priya@acme.local"}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Finance"
    assert data["sector"] == "banking"
    assert data["contacts"][0]["name"] == "Priya"


def test_list_clients(client):
    resp = client.get("/clients/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_update_client(client):
    r = client.post("/clients/", json={"name": "Temp Corp"})
    assert r.status_code == 201
    cid = r.json()["id"]
    resp = client.patch(f"/clients/{cid}", json={"regulatory_context": "DPDP Act 2023"})
    assert resp.status_code == 200
    assert resp.json()["regulatory_context"] == "DPDP Act 2023"


def test_create_project(client):
    # Create client first
    c_resp = client.post("/clients/", json={"name": "Project Owner Corp"})
    cid = c_resp.json()["id"]

    resp = client.post("/projects/", json={
        "client_id": cid,
        "service_type": "dpdp",
        "scope_summary": "Full DPDP readiness",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["client_id"] == cid
    assert data["service_type"] == "dpdp"
    assert data["status"] == "setup"
    assert data["gates"]["G1_scope"] is False


def test_project_not_found(client):
    resp = client.get("/projects/nonexistent-id")
    assert resp.status_code == 404


def test_scope_item_starts_unapproved(client, SessionTest):
    """Add an exclusion scope item — must start unapproved, return ApprovalRequest."""
    c_resp = client.post("/clients/", json={"name": "Scope Test Corp"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]

    resp = client.post(f"/projects/{pid}/scope/", json={
        "kind": "exclusion",
        "value": "PCI-DSS cardholder data environment",
        "reason": "Out of scope per engagement letter",
    })
    assert resp.status_code == 201
    approval = resp.json()
    assert approval["status"] == "pending"
    assert approval["target_type"] == "scope_item"

    # Scope item itself must be unapproved
    with SessionTest() as db:
        item = db.get(ScopeItem, approval["target_id"])
    assert item is not None
    assert item.approved is False



def test_approve_scope_item_via_gateway(client, SessionTest):
    """Decide an approval → scope_item.approved flips True + audit event written."""
    c_resp = client.post("/clients/", json={"name": "Gate Corp"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "vapt"})
    pid = p_resp.json()["id"]

    # Add scope item
    scope_resp = client.post(f"/projects/{pid}/scope/", json={
        "kind": "asset",
        "value": "app.example.com",
        "reason": "Primary target",
    })
    approval_id = scope_resp.json()["id"]
    item_id = scope_resp.json()["target_id"]

    # Decide: approved
    decide_resp = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Scope confirmed by PM",
    })
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "approved"

    # ScopeItem.approved must now be True
    with SessionTest() as db:
        item = db.get(ScopeItem, item_id)
        events = (
            db.query(AuditTrailEvent)
            .filter_by(project_id=pid)
            .all()
        )
    assert item.approved is True

    actions = [e.action for e in events]
    assert any("approval.requested" in a for a in actions)
    assert any("approval.approved" in a for a in actions)


def test_reject_scope_item(client, SessionTest):
    """Reject a scope item — approved stays False."""
    c_resp = client.post("/clients/", json={"name": "Reject Corp"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]

    scope_resp = client.post(f"/projects/{pid}/scope/", json={
        "kind": "inclusion",
        "value": "HR system",
    })
    approval_id = scope_resp.json()["id"]
    item_id = scope_resp.json()["target_id"]

    decide_resp = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": False,
        "reason": "HR system moved to separate engagement",
    })
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "rejected"

    with SessionTest() as db:
        item = db.get(ScopeItem, item_id)
    assert item.approved is False


def test_double_decide_rejected(client):
    """Deciding an already-decided approval returns 400."""
    c_resp = client.post("/clients/", json={"name": "DD Corp"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]

    scope_resp = client.post(f"/projects/{pid}/scope/", json={"kind": "asset", "value": "x"})
    aid = scope_resp.json()["id"]

    client.post(f"/approvals/{aid}/decide", json={"approved": True})
    resp = client.post(f"/approvals/{aid}/decide", json={"approved": True})
    assert resp.status_code == 400


def test_list_approvals_filter_by_project(client):
    c_resp = client.post("/clients/", json={"name": "Filter Corp"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]

    client.post(f"/projects/{pid}/scope/", json={"kind": "assumption", "value": "prod only"})

    resp = client.get(f"/approvals/?project_id={pid}&status=pending")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert all(r["project_id"] == pid for r in results)
    assert all(r["status"] == "pending" for r in results)
