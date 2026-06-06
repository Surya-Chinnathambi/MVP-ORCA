"""Stage 7 acceptance test — findings register."""
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
from app.models.evidence import EvidenceItem
from app.models.tasks import Finding


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
    with Session(engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        db.flush()
        admin_role = db.query(Role).filter_by(name=RoleName.platform_admin).first()
        admin = User(
            email="admin@stage7.local",
            password_hash=hash_password("admin123"),
            full_name="Stage7 Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))

        client_row = Client(entity_name="Stage7 Corp")
        db.add(client_row)
        db.flush()
        project = Project(
            client_id=client_row.id,
            service_type=ServiceType.vapt,
            pack_id="vapt",
        )
        db.add(project)
        db.flush()
        pack = load_pack("vapt")
        generate_plan(db, project, pack)

        # Seed a dummy EvidenceItem for linking
        ev_item = EvidenceItem(
            project_id=project.id,
            source_file="nmap_output.txt",
            sha256="a" * 64,
            mime="text/plain",
            reviewer_status="pending",
        )
        db.add(ev_item)
        db.commit()
        yield {
            "admin_id": admin.id,
            "project_id": project.id,
            "ev_item_id": ev_item.id,
        }


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
        c.post("/auth/login", json={"email": "admin@stage7.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_finding_blank(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/findings/", json={
        "title": "Weak TLS configuration",
        "severity": "medium",
        "description": "TLS 1.0 still enabled on web server.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Weak TLS configuration"
    assert data["severity"] == "medium"
    assert data["status"] == "open"
    assert data["source"] == "manual"


def test_create_finding_with_evidence(client, seeded):
    pid = seeded["project_id"]
    ev_id = seeded["ev_item_id"]
    resp = client.post(f"/projects/{pid}/findings/", json={
        "title": "SQL Injection in login form",
        "severity": "high",
        "evidence_item_ids": [ev_id],
        "source": "manual",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert ev_id in data["evidence_item_ids"]
    assert data["severity"] == "high"


def test_create_finding_invalid_severity(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/findings/", json={
        "title": "Bad finding",
        "severity": "catastrophic",
    })
    assert resp.status_code == 422


def test_create_finding_ptorc_source(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/findings/", json={
        "title": "Open redirect via PT-Orc",
        "severity": "low",
        "source": "ptorc",
    })
    assert resp.status_code == 201
    assert resp.json()["source"] == "ptorc"


def test_create_finding_linked_to_requirement(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        from app.models.scope import Requirement
        req = db.query(Requirement).filter_by(project_id=pid).first()
    resp = client.post(f"/projects/{pid}/findings/", json={
        "title": "Missing auth rate limiting",
        "severity": "high",
        "requirement_id": req.id,
    })
    assert resp.status_code == 201
    assert resp.json()["requirement_id"] == req.id


# ── Severity change (approval-gated) ─────────────────────────────────────────

def test_severity_change_returns_approval(client, seeded, SessionTest):
    pid = seeded["project_id"]
    # Create a medium finding
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "XSS in search input",
        "severity": "medium",
    }).json()["id"]

    resp = client.post(f"/projects/{pid}/findings/{fid}/change-severity", json={
        "severity": "high",
        "reason": "Confirmed exploitable via stored XSS vector",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["target_type"] == "finding_severity_change"
    assert data["target_id"] == fid
    assert data["change_before"] == {"severity": "medium"}
    assert data["change_after"] == {"severity": "high"}

    # Finding is still medium — approval pending
    with SessionTest() as db:
        f = db.get(Finding, fid)
    assert f.severity == "medium"


def test_approve_severity_change_flips_finding(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Insecure direct object reference",
        "severity": "low",
    }).json()["id"]

    approval_id = client.post(f"/projects/{pid}/findings/{fid}/change-severity", json={
        "severity": "critical",
        "reason": "Allows account takeover",
    }).json()["id"]

    decide = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Verified critical impact",
    })
    assert decide.status_code == 200
    assert decide.json()["status"] == "approved"

    with SessionTest() as db:
        f = db.get(Finding, fid)
    assert f.severity == "critical"


def test_reject_severity_change_leaves_finding_unchanged(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Clickjacking vulnerability",
        "severity": "low",
    }).json()["id"]

    approval_id = client.post(f"/projects/{pid}/findings/{fid}/change-severity", json={
        "severity": "high",
        "reason": "Reassessing impact",
    }).json()["id"]

    client.post(f"/approvals/{approval_id}/decide", json={
        "approved": False,
        "reason": "Disagree — impact not verified",
    })

    with SessionTest() as db:
        f = db.get(Finding, fid)
    assert f.severity == "low"  # unchanged


def test_same_severity_is_rejected(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Duplicate severity test",
        "severity": "medium",
    }).json()["id"]

    resp = client.post(f"/projects/{pid}/findings/{fid}/change-severity", json={
        "severity": "medium",
        "reason": "Same as existing",
    })
    assert resp.status_code == 400


# ── Status change (approval-gated) ───────────────────────────────────────────

def test_status_change_returns_approval(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Session fixation",
        "severity": "high",
    }).json()["id"]

    resp = client.post(f"/projects/{pid}/findings/{fid}/change-status", json={
        "status": "in_review",
        "reason": "Ready for reviewer assessment",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["target_type"] == "finding_status_change"
    assert data["change_before"] == {"status": "open"}
    assert data["change_after"] == {"status": "in_review"}


def test_approve_status_change(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "CSRF missing token",
        "severity": "medium",
    }).json()["id"]

    approval_id = client.post(f"/projects/{pid}/findings/{fid}/change-status", json={
        "status": "approved",
        "reason": "Verified by reviewer",
    }).json()["id"]

    client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Confirmed",
    })

    with SessionTest() as db:
        f = db.get(Finding, fid)
    assert f.status == "approved"


# ── Non-gated update ──────────────────────────────────────────────────────────

def test_patch_description_direct(client, seeded, SessionTest):
    pid = seeded["project_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Missing security headers",
        "severity": "info",
    }).json()["id"]

    resp = client.patch(f"/projects/{pid}/findings/{fid}", json={
        "description": "X-Frame-Options header not set on login page.",
    })
    assert resp.status_code == 200
    assert "X-Frame-Options" in resp.json()["description"]

    with SessionTest() as db:
        f = db.get(Finding, fid)
    assert "X-Frame-Options" in f.description


def test_patch_evidence_item_ids(client, seeded, SessionTest):
    pid = seeded["project_id"]
    ev_id = seeded["ev_item_id"]
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "Outdated dependencies",
        "severity": "medium",
    }).json()["id"]

    resp = client.patch(f"/projects/{pid}/findings/{fid}", json={
        "evidence_item_ids": [ev_id],
    })
    assert resp.status_code == 200
    assert ev_id in resp.json()["evidence_item_ids"]


# ── Filter views ──────────────────────────────────────────────────────────────

def test_list_findings_by_severity(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/findings/?severity=high")
    assert resp.status_code == 200
    assert all(f["severity"] == "high" for f in resp.json())


def test_list_findings_by_source(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/findings/?source=ptorc")
    assert resp.status_code == 200
    assert all(f["source"] == "ptorc" for f in resp.json())


def test_list_findings_by_status(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/findings/?status=open")
    assert resp.status_code == 200
    assert all(f["status"] == "open" for f in resp.json())


def test_list_all_findings(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/findings/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4
