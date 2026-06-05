"""Stage 8 acceptance test — gate tracker + QA agent."""
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
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
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
        admin_role = db.query(Role).filter_by(name=RoleName.admin).first()
        admin = User(
            email="admin@stage8.local",
            password_hash=hash_password("admin123"),
            full_name="Stage8 Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))

        client_row = Client(name="Stage8 Corp")
        db.add(client_row)
        db.flush()
        project = Project(
            client_id=client_row.id,
            service_type=ServiceType.dpdp,
            pack_id="dpdp",
            gates={
                "G1_scope": False, "G2_evidence_requests": False,
                "G3_evidence_complete": False, "G4_findings": False,
                "G5_qa": False, "G6_report": False, "G7_closure": False,
            },
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
        c.post("/auth/login", json={"email": "admin@stage8.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Gate initial state ────────────────────────────────────────────────────────

def test_all_gates_start_closed(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/gates/")
    assert resp.status_code == 200
    gates = resp.json()["gates"]
    assert gates == {
        "G1_scope": False,
        "G2_evidence_requests": False,
        "G3_evidence_complete": False,
        "G4_findings": False,
        "G5_qa": False,
        "G6_report": False,
        "G7_closure": False,
    }


# ── G1: scope gate ────────────────────────────────────────────────────────────

def test_g1_blocked_with_no_approved_scope(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/gates/G1_scope/advance")
    assert resp.status_code == 400
    assert "scope" in resp.json()["detail"].lower()


def test_g1_passes_after_scope_approval(client, seeded, SessionTest):
    """G1 can only advance once a scope item has been approved via the gateway."""
    pid = seeded["project_id"]

    # Add a scope item and approve it via the gateway
    add_resp = client.post(f"/projects/{pid}/scope/", json={
        "kind": "asset",
        "value": "web-app-prod",
        "reason": "Production web application",
    })
    assert add_resp.status_code == 201
    approval_id = add_resp.json()["id"]   # scope returns ApprovalOut

    # Approve the scope item
    decide_resp = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Confirmed in scope",
    })
    assert decide_resp.status_code == 200

    # Now G1 can advance
    advance_resp = client.post(f"/projects/{pid}/gates/G1_scope/advance")
    assert advance_resp.status_code == 200
    assert advance_resp.json()["gates"]["G1_scope"] is True


def test_g1_already_passed_returns_400(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/gates/G1_scope/advance")
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


# ── G2: evidence request list gate ───────────────────────────────────────────

def test_g2_blocked_while_ers_open(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/gates/G2_evidence_requests/advance")
    assert resp.status_code == 400
    assert "open" in resp.json()["detail"].lower()


def test_g2_passes_after_all_ers_closed(client, seeded, SessionTest):
    pid = seeded["project_id"]
    # Mark all ERs as received
    with SessionTest() as db:
        ers = db.query(EvidenceRequest).filter_by(project_id=pid).all()
    for er in ers:
        client.patch(
            f"/projects/{pid}/evidence-requests/{er.id}",
            json={"status": "received"},
        )
    resp = client.post(f"/projects/{pid}/gates/G2_evidence_requests/advance")
    assert resp.status_code == 200
    assert resp.json()["gates"]["G2_evidence_requests"] is True


# ── G3: evidence complete ─────────────────────────────────────────────────────

def test_g3_blocked_without_evidence_items(client, seeded, SessionTest):
    pid = seeded["project_id"]
    # G2 passed (all ERs received), but no evidence items uploaded
    resp = client.post(f"/projects/{pid}/gates/G3_evidence_complete/advance")
    assert resp.status_code == 400
    assert "evidence" in resp.json()["detail"].lower()


def test_g3_passes_after_upload(client, seeded):
    pid = seeded["project_id"]
    from PIL import Image
    import io
    img = Image.new("RGB", (8, 8), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("doc.png", buf.getvalue(), "image/png")},
    )
    resp = client.post(f"/projects/{pid}/gates/G3_evidence_complete/advance")
    assert resp.status_code == 200
    assert resp.json()["gates"]["G3_evidence_complete"] is True


# ── G4: findings gate ─────────────────────────────────────────────────────────

def test_g4_blocked_without_findings(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/gates/G4_findings/advance")
    assert resp.status_code == 400


def test_g4_blocked_with_open_finding(client, seeded, SessionTest):
    pid = seeded["project_id"]
    client.post(f"/projects/{pid}/findings/", json={
        "title": "Open finding for G4 test",
        "severity": "medium",
        "evidence_item_ids": [],
    })
    resp = client.post(f"/projects/{pid}/gates/G4_findings/advance")
    assert resp.status_code == 400
    assert "finding" in resp.json()["detail"].lower()


def test_g4_passes_after_all_findings_approved(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        findings = db.query(Finding).filter_by(project_id=pid).all()

    for f in findings:
        approval_id = client.post(
            f"/projects/{pid}/findings/{f.id}/change-status",
            json={"status": "approved", "reason": "Reviewed"},
        ).json()["id"]
        client.post(f"/approvals/{approval_id}/decide", json={
            "approved": True,
            "reason": "OK",
        })

    resp = client.post(f"/projects/{pid}/gates/G4_findings/advance")
    assert resp.status_code == 200
    assert resp.json()["gates"]["G4_findings"] is True


# ── QA agent ──────────────────────────────────────────────────────────────────

def test_qa_flags_finding_without_evidence(client, seeded, SessionTest):
    """Core acceptance test: finding with no evidence → QA flags it."""
    pid = seeded["project_id"]
    # Create a finding with no evidence
    fid = client.post(f"/projects/{pid}/findings/", json={
        "title": "No-evidence finding",
        "severity": "high",
    }).json()["id"]

    resp = client.post(f"/projects/{pid}/qa/run")
    assert resp.status_code == 200
    report = resp.json()
    assert report["project_id"] == pid
    assert "every_finding_has_evidence" in report["rules_run"]
    assert report["passed"] is False

    error_rules = [i["rule"] for i in report["issues"] if i["severity"] == "error"]
    assert "every_finding_has_evidence" in error_rules

    # The no-evidence finding is named in the issue
    issue = next(i for i in report["issues"] if i["rule"] == "every_finding_has_evidence")
    assert fid in issue["item_ids"]


def test_qa_passes_when_all_findings_have_evidence(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        ev = db.query(EvidenceItem).filter_by(project_id=pid).first()
        all_findings = db.query(Finding).filter_by(project_id=pid).all()

    # Attach evidence to every finding
    for f in all_findings:
        client.patch(f"/projects/{pid}/findings/{f.id}", json={
            "evidence_item_ids": [ev.id],
        })

    resp = client.post(f"/projects/{pid}/qa/run")
    report = resp.json()
    error_rules = [i["rule"] for i in report["issues"] if i["severity"] == "error"]
    assert "every_finding_has_evidence" not in error_rules


def test_qa_flags_open_evidence_requests(client, seeded, SessionTest):
    """Add a fresh ER so the open-ER rule fires."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = EvidenceRequest(
            project_id=pid,
            title="Late ER for QA test",
            status=EvidenceRequestStatus.open,
        )
        db.add(er)
        db.commit()

    resp = client.post(f"/projects/{pid}/qa/run")
    report = resp.json()
    warning_rules = [i["rule"] for i in report["issues"] if i["severity"] == "warning"]
    assert "open_evidence_requests_flagged" in warning_rules


def test_qa_runs_only_pack_rules(client, seeded):
    """DPDP pack has 4 rules — exactly those should appear in rules_run."""
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/qa/run")
    report = resp.json()
    expected = {
        "every_finding_has_evidence",
        "severity_consistent",
        "all_requirements_assessed",
        "open_evidence_requests_flagged",
    }
    assert set(report["rules_run"]) == expected


# ── G5 gate: QA must pass ─────────────────────────────────────────────────────

def test_g5_blocked_when_qa_has_errors(client, seeded, SessionTest):
    """While every_finding_has_evidence errors remain, G5 cannot advance."""
    pid = seeded["project_id"]
    # Create a finding with no evidence to ensure QA error exists
    client.post(f"/projects/{pid}/findings/", json={
        "title": "No-evidence blocker for G5",
        "severity": "low",
    })
    resp = client.post(f"/projects/{pid}/gates/G5_qa/advance")
    assert resp.status_code == 400
    assert "qa" in resp.json()["detail"].lower() or "G4" in resp.json()["detail"]


# ── Unknown gate ──────────────────────────────────────────────────────────────

def test_unknown_gate_returns_400(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(f"/projects/{pid}/gates/G99_fantasy/advance")
    assert resp.status_code == 400
