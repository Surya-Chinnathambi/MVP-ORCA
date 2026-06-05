"""Stage 5 acceptance test — requirements tracker, task board, ER tracker."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app as fastapi_app
from app.services.auth import hash_password
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan

import app.models  # noqa: F401
from app.models.users import Role, RoleName, User, Permission
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.tasks import Task
from app.models.workflow import ApprovalStatus

# ── Fixtures ─────────────────────────────────────────────────────────────────

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
def seeded(engine, SessionTest):
    """Seed roles, admin user, and a DPDP project with full plan generated."""
    with Session(engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        db.flush()
        admin_role = db.query(Role).filter_by(name=RoleName.admin).first()
        admin = User(
            email="admin@stage5.local",
            password_hash=hash_password("admin123"),
            full_name="Stage5 Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))

        # Create client + DPDP project with plan
        client_row = Client(name="Stage5 Corp")
        db.add(client_row)
        db.flush()
        project = Project(
            client_id=client_row.id,
            service_type=ServiceType.dpdp,
            pack_id="dpdp",
        )
        db.add(project)
        db.flush()
        pack = load_pack("dpdp")
        generate_plan(db, project, pack)
        db.commit()

        yield {"admin_id": admin.id, "project_id": project.id}


@pytest.fixture(scope="module")
def client(seeded, SessionTest):
    def override():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app) as c:
        c.post("/auth/login", json={"email": "admin@stage5.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Requirements tracker ──────────────────────────────────────────────────────

def test_list_all_requirements(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/requirements/")
    assert resp.status_code == 200
    reqs = resp.json()
    assert len(reqs) == 12
    # Sorted by ref_code
    ref_codes = [r["ref_code"] for r in reqs]
    assert ref_codes == sorted(ref_codes)


def test_filter_requirements_by_category(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/requirements/?category=notice")
    assert resp.status_code == 200
    reqs = resp.json()
    assert len(reqs) == 2
    assert all(r["category"] == "notice" for r in reqs)


def test_list_requirement_categories(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/requirements/categories/list")
    assert resp.status_code == 200
    cats = resp.json()
    expected = {"notice", "consent", "rights", "security", "breach", "governance"}
    assert expected == set(cats)


def test_get_single_requirement(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        req = db.query(__import__("app.models.scope", fromlist=["Requirement"]).Requirement
                       ).filter_by(project_id=pid, ref_code="DPDP-NOTICE-01").first()
    resp = client.get(f"/projects/{pid}/requirements/{req.id}")
    assert resp.status_code == 200
    assert resp.json()["ref_code"] == "DPDP-NOTICE-01"


# ── Task board ────────────────────────────────────────────────────────────────

def test_list_tasks(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/tasks/")
    assert resp.status_code == 200
    assert len(resp.json()) == 8


def test_task_status_open_to_done(client, seeded, SessionTest):
    """Direct status transition open → done (non-gated)."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        task = db.query(Task).filter_by(project_id=pid, status="open").first()
    tid = task.id

    resp = client.patch(f"/projects/{pid}/tasks/{tid}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["id"] == tid


def test_task_status_open_to_in_progress(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        task = db.query(Task).filter_by(project_id=pid, status="open").first()
    tid = task.id

    resp = client.patch(f"/projects/{pid}/tasks/{tid}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_task_cancellation_requires_approval(client, seeded, SessionTest):
    """Cancellation must return a pending ApprovalRequest, not a TaskOut."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        task = db.query(Task).filter_by(project_id=pid, status="open").first()
    tid = task.id

    resp = client.patch(f"/projects/{pid}/tasks/{tid}", json={"status": "cancelled"})
    assert resp.status_code == 200
    data = resp.json()
    # Should return an ApprovalRequest (has 'approver_role' and 'target_type')
    assert data["status"] == "pending"
    assert data["target_type"] == "task_cancellation"
    assert data["target_id"] == tid

    # Task is NOT yet cancelled — approval is pending
    with SessionTest() as db:
        task_now = db.get(Task, tid)
    assert task_now.status != "cancelled"


def test_task_invalid_status(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        task = db.query(Task).filter_by(project_id=pid).first()
    resp = client.patch(f"/projects/{pid}/tasks/{task.id}", json={"status": "flying"})
    assert resp.status_code == 422


def test_create_task(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/tasks/", json={
        "kind": "interview",
        "title": "Extra security interview",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "open"


def test_filter_tasks_by_status(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/tasks/?status=open")
    assert resp.status_code == 200
    assert all(t["status"] == "open" for t in resp.json())


# ── Evidence-request tracker ──────────────────────────────────────────────────

def test_list_evidence_requests(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/evidence-requests/")
    assert resp.status_code == 200
    assert len(resp.json()) == 12


def test_mark_er_received(client, seeded, SessionTest):
    """Marking as received is a direct update (no approval)."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid, status="open").first()
    er_id = er.id

    resp = client.patch(f"/projects/{pid}/evidence-requests/{er_id}", json={"status": "received"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"


def test_waive_er_requires_approval(client, seeded, SessionTest):
    """Waiving an ER returns a pending ApprovalRequest; status stays open."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid, status="open").first()
    er_id = er.id

    resp = client.post(
        f"/projects/{pid}/evidence-requests/{er_id}/waive",
        json={"reason": "Vendor system not in scope after descoping decision"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["target_type"] == "evidence_request_waiver"
    assert data["target_id"] == er_id

    # ER is still open — not yet waived
    with SessionTest() as db:
        er_now = db.get(EvidenceRequest, er_id)
    assert er_now.status == EvidenceRequestStatus.open


def test_approve_waiver_flips_status(client, seeded, SessionTest):
    """Approve the waiver → ER status becomes 'waived'."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid, status="open").first()
    er_id = er.id

    # Request waiver
    waive_resp = client.post(
        f"/projects/{pid}/evidence-requests/{er_id}/waive",
        json={"reason": "Not applicable per engagement scope"},
    )
    approval_id = waive_resp.json()["id"]

    # Approve it
    decide_resp = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Confirmed out of scope",
    })
    assert decide_resp.status_code == 200
    assert decide_resp.json()["status"] == "approved"

    # ER is now waived
    with SessionTest() as db:
        er_now = db.get(EvidenceRequest, er_id)
    assert er_now.status == EvidenceRequestStatus.waived


def test_direct_waive_via_patch_is_blocked(client, seeded, SessionTest):
    """PATCH with status=waived is rejected — must use /waive endpoint."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid, status="open").first()
    resp = client.patch(
        f"/projects/{pid}/evidence-requests/{er.id}",
        json={"status": "waived"},
    )
    assert resp.status_code == 400


def test_filter_ers_by_status(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/evidence-requests/?status=open")
    assert resp.status_code == 200
    assert all(e["status"] == "open" for e in resp.json())
