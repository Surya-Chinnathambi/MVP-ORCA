"""Stage 28 acceptance test — client portal.

Verifies:
1.  Unauthenticated GET /portal/dashboard → 401.
2.  Non-portal user (analyst) → 403 from /portal/dashboard.
3.  client_contributor with scoped permission → 200 from /portal/dashboard.
4.  Dashboard shows only client_shared findings for the scoped project.
5.  Dashboard does NOT show findings from another project.
6.  Upload creates an EvidenceItem with internal_lifecycle_state = "intake".
7.  POST /portal/accept-risk/{finding_id} creates a pending ApprovalRequest
    and does NOT change the finding status.
8.  POST /portal/tasks/{task_id}/comment records an AuditTrailEvent.
9.  POST /portal/questions/{er_id}/answer appends answer to description.
10. Portal user cannot reach an internal page requiring analyst role (403).
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base, get_db
from app.main import app as fastapi_app
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceItem, EvidenceLifecycleState, EvidenceRequest
from app.models.organization import Organization
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus, Task, TaskKind, TaskStatus
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent
from app.services.auth import hash_password


# ── Test DB fixture ───────────────────────────────────────────────────────────

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
def _SessionLocal(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def seeded(engine, _SessionLocal):
    """Seed all roles, two users, two projects, findings, tasks, evidence request."""
    with Session(engine) as db:
        # Seed all roles
        role_map = {}
        for rname in [r.value for r in RoleName]:
            role = Role(name=rname)
            db.add(role)
            db.flush()
            role_map[rname] = role

        org = Organization(name="S28 Org")
        db.add(org)
        db.flush()

        client_obj = Client(name="S28 Client", organization_id=org.id)
        db.add(client_obj)
        db.flush()

        # Project A — the portal user's project
        proj_a = Project(client_id=client_obj.id, service_type=ServiceType.vapt, status="active")
        db.add(proj_a)
        db.flush()

        # Project B — another project the portal user must NOT see
        proj_b = Project(client_id=client_obj.id, service_type=ServiceType.vapt, status="active")
        db.add(proj_b)
        db.flush()

        # Portal user: client_contributor scoped to proj_a
        portal_user = User(
            email="portal@test.local",
            password_hash=hash_password("portpass"),
            full_name="Portal Contrib",
            is_active=True,
        )
        db.add(portal_user)
        db.flush()
        db.add(Permission(
            user_id=portal_user.id,
            role_id=role_map[RoleName.client_contributor.value].id,
            scope_level=ScopeLevel.project.value,
            scope_id=proj_a.id,
        ))

        # Analyst user: NOT a portal role
        analyst_user = User(
            email="analyst28@test.local",
            password_hash=hash_password("analpass"),
            full_name="Analyst S28",
            is_active=True,
        )
        db.add(analyst_user)
        db.flush()
        db.add(Permission(
            user_id=analyst_user.id,
            role_id=role_map[RoleName.analyst.value].id,
            scope_level=ScopeLevel.project.value,
            scope_id=proj_a.id,
        ))

        # Finding in proj_a — client_shared (visible in portal)
        shared_finding = Finding(
            project_id=proj_a.id,
            title="Shared Finding A",
            severity=FindingSeverity.high.value,
            status=FindingStatus.client_shared.value,
            source=FindingSource.manual.value,
        )
        db.add(shared_finding)
        # Finding in proj_a — draft (NOT visible in portal)
        draft_finding = Finding(
            project_id=proj_a.id,
            title="Draft Finding A",
            severity=FindingSeverity.low.value,
            status=FindingStatus.draft.value,
            source=FindingSource.manual.value,
        )
        db.add(draft_finding)
        # Finding in proj_b — should not be visible to portal user
        other_finding = Finding(
            project_id=proj_b.id,
            title="Finding Proj B",
            severity=FindingSeverity.medium.value,
            status=FindingStatus.client_shared.value,
            source=FindingSource.manual.value,
        )
        db.add(other_finding)
        db.flush()

        # Task in proj_a
        task_a = Task(
            project_id=proj_a.id,
            kind=TaskKind.review.value,
            title="Client Sign-off Task",
            status=TaskStatus.review.value,
        )
        db.add(task_a)

        # Evidence request in proj_a
        er_a = EvidenceRequest(
            project_id=proj_a.id,
            title="Provide network diagram",
        )
        db.add(er_a)
        db.flush()

        db.commit()

        yield {
            "portal_user_id": portal_user.id,
            "analyst_user_id": analyst_user.id,
            "proj_a_id": proj_a.id,
            "proj_b_id": proj_b.id,
            "shared_finding_id": shared_finding.id,
            "draft_finding_id": draft_finding.id,
            "other_finding_id": other_finding.id,
            "task_a_id": task_a.id,
            "er_a_id": er_a.id,
        }


@pytest.fixture(scope="module")
def portal_client(seeded, _SessionLocal):
    """TestClient logged in as the client_contributor portal user."""
    def override():
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app, follow_redirects=True) as c:
        resp = c.post("/auth/login", json={"email": "portal@test.local", "password": "portpass"})
        assert resp.status_code == 200, resp.text
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def analyst_client(seeded, _SessionLocal):
    """TestClient logged in as the non-portal analyst user."""
    def override():
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app, follow_redirects=True) as c:
        resp = c.post("/auth/login", json={"email": "analyst28@test.local", "password": "analpass"})
        assert resp.status_code == 200, resp.text
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def db_session(engine, _SessionLocal):
    s = _SessionLocal()
    yield s
    s.close()


# ── 1. Unauthenticated → 401 ──────────────────────────────────────────────────

def test_unauthenticated_portal_401(engine, _SessionLocal):
    def override():
        db = _SessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app, follow_redirects=False) as c:
        resp = c.get("/portal/dashboard")
    fastapi_app.dependency_overrides.clear()
    assert resp.status_code in (401, 302, 303)


# ── 2. Non-portal user → 403 ─────────────────────────────────────────────────

def test_analyst_cannot_access_portal(analyst_client):
    resp = analyst_client.get("/portal/dashboard")
    assert resp.status_code == 403


# ── 3. Portal user → 200 ──────────────────────────────────────────────────────

def test_portal_dashboard_ok(portal_client):
    resp = portal_client.get("/portal/dashboard")
    assert resp.status_code == 200
    assert "Shared Finding A" in resp.text


# ── 4. Dashboard shows only client_shared findings for scoped project ─────────

def test_dashboard_shows_shared_not_draft(portal_client):
    resp = portal_client.get("/portal/dashboard")
    assert "Shared Finding A" in resp.text
    assert "Draft Finding A" not in resp.text


# ── 5. Dashboard does NOT show findings from another project ──────────────────

def test_dashboard_excludes_other_project(portal_client):
    resp = portal_client.get("/portal/dashboard")
    assert "Finding Proj B" not in resp.text


# ── 6. Upload creates EvidenceItem at intake state ────────────────────────────

def test_upload_creates_intake_item(portal_client, db_session, seeded):
    before_count = db_session.query(EvidenceItem).filter_by(
        project_id=seeded["proj_a_id"]
    ).count()

    resp = portal_client.post(
        "/portal/upload",
        data={"evidence_request_id": ""},
        files={"file": ("test.txt", io.BytesIO(b"Network diagram content"), "text/plain")},
    )
    assert resp.status_code == 200
    assert "uploaded successfully" in resp.text

    db_session.expire_all()
    after_count = db_session.query(EvidenceItem).filter_by(
        project_id=seeded["proj_a_id"]
    ).count()
    assert after_count == before_count + 1

    item = (
        db_session.query(EvidenceItem)
        .filter_by(project_id=seeded["proj_a_id"])
        .order_by(EvidenceItem.created_at.desc())
        .first()
    )
    assert item is not None
    assert item.internal_lifecycle_state == EvidenceLifecycleState.intake.value


# ── 7. Accept-risk creates ApprovalRequest, does NOT change finding status ────

def test_accept_risk_creates_pending_approval(portal_client, db_session, seeded):
    finding_id = seeded["shared_finding_id"]
    finding_before = db_session.get(Finding, finding_id)
    status_before = finding_before.status

    resp = portal_client.post(f"/portal/accept-risk/{finding_id}")
    assert resp.status_code in (200, 302, 303)

    db_session.expire_all()
    # Status must NOT have changed
    finding_after = db_session.get(Finding, finding_id)
    assert finding_after.status == status_before

    # ApprovalRequest must exist with status=pending
    approval = (
        db_session.query(ApprovalRequest)
        .filter_by(
            project_id=seeded["proj_a_id"],
            target_type="finding",
            target_id=finding_id,
        )
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )
    assert approval is not None
    assert approval.status == ApprovalStatus.pending


# ── 8. Task comment records AuditTrailEvent ───────────────────────────────────

def test_task_comment_records_event(portal_client, db_session, seeded):
    task_id = seeded["task_a_id"]
    before_count = db_session.query(AuditTrailEvent).filter_by(
        target_type="task", target_id=task_id
    ).count()

    resp = portal_client.post(
        f"/portal/tasks/{task_id}/comment",
        data={"comment": "We need two more weeks for remediation."},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    after_count = db_session.query(AuditTrailEvent).filter_by(
        target_type="task", target_id=task_id
    ).count()
    assert after_count == before_count + 1


# ── 9. Questions answer appends to description ────────────────────────────────

def test_questions_answer_updates_description(portal_client, db_session, seeded):
    er_id = seeded["er_a_id"]
    resp = portal_client.post(
        f"/portal/questions/{er_id}/answer",
        data={"answer": "Here is the network diagram link: internal.example.com/net"},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    er = db_session.get(EvidenceRequest, er_id)
    assert er.description is not None
    assert "network diagram link" in er.description


# ── 10. Portal user cannot reach admin-protected API endpoints ────────────────

def test_portal_user_cannot_reach_admin_api(portal_client):
    """Portal role is not admin — API requires admin should return 403."""
    resp = portal_client.get("/users/")
    assert resp.status_code == 403
