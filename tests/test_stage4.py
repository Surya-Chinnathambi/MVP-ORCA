"""Stage 4 acceptance test — pack loader, plan generator, methodology API."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app as fastapi_app
from app.services.auth import hash_password
from app.services.methodology.loader import Pack, load_pack, available_packs
from app.services.methodology.plan import generate_plan

import app.models  # noqa: F401
from app.models.users import Role, RoleName, User, Permission
from app.models.clients import Client, Project, ServiceType
from app.models.scope import Framework, Requirement
from app.models.evidence import EvidenceRequest
from app.models.tasks import Task

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
            email="admin@stage4.local",
            password_hash=hash_password("admin123"),
            full_name="Stage4 Admin",
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
        c.post("/auth/login", json={"email": "admin@stage4.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Pack loader tests ─────────────────────────────────────────────────────────

def test_available_packs():
    packs = available_packs()
    assert "dpdp" in packs
    assert "vapt" in packs


def test_load_dpdp_pack():
    pack = load_pack("dpdp")
    assert pack.key == "dpdp"
    assert pack.frameworks == ["dpdp_act"]
    assert len(pack.requirements) == 12
    assert len(pack.evidence_requests) == 12
    assert len(pack.task_templates) == 8
    assert len(pack.intake_questions) >= 3
    assert len(pack.qa_rules) >= 2
    # Every evidence request references a valid requirement
    ref_codes = {r.ref_code for r in pack.requirements}
    for er in pack.evidence_requests:
        assert er.requirement_ref in ref_codes, f"{er.requirement_ref} not in requirements"


def test_load_vapt_pack():
    pack = load_pack("vapt")
    assert pack.key == "vapt"
    assert "owasp_wstg" in pack.frameworks
    assert len(pack.requirements) == 12
    assert len(pack.task_templates) >= 8


def test_pack_not_found():
    with pytest.raises(FileNotFoundError):
        load_pack("nonexistent_pack")


def test_pack_schema_is_pydantic(monkeypatch, tmp_path):
    """A pack with missing required field raises ValidationError."""
    import json
    bad = tmp_path / "bad" / "pack.json"
    bad.parent.mkdir()
    bad.write_text(json.dumps({"key": "bad", "title": "Bad"}))  # missing 'requirements' and 'frameworks'
    from pydantic import ValidationError
    from app.services.methodology import loader as loader_mod
    orig = loader_mod._PACKS_DIR
    loader_mod._PACKS_DIR = tmp_path
    try:
        with pytest.raises(ValidationError):
            load_pack("bad")
    finally:
        loader_mod._PACKS_DIR = orig


# ── Plan generator tests ──────────────────────────────────────────────────────

def test_generate_dpdp_plan(SessionTest):
    """generate_plan creates correct requirement/ER/task counts for DPDP."""
    pack = load_pack("dpdp")
    with SessionTest() as db:
        client_row = Client(name="Plan Test Corp DPDP")
        db.add(client_row)
        db.flush()
        project = Project(
            client_id=client_row.id,
            service_type=ServiceType.dpdp,
            pack_id="dpdp",
        )
        db.add(project)
        db.flush()

        summary = generate_plan(db, project, pack)
        db.commit()

        assert summary.requirements_created == 12
        assert summary.evidence_requests_created == 12
        assert summary.tasks_created == 8

        # Verify rows are actually in DB and linked to the project
        reqs = db.query(Requirement).filter_by(project_id=project.id).all()
        ers  = db.query(EvidenceRequest).filter_by(project_id=project.id).all()
        tasks = db.query(Task).filter_by(project_id=project.id).all()
        assert len(reqs) == 12
        assert len(ers) == 12
        assert len(tasks) == 8

        # Framework row created
        fw = db.query(Framework).filter_by(key="dpdp_act").first()
        assert fw is not None

        # All requirements linked to the project's framework
        for r in reqs:
            assert r.project_id == project.id
            assert r.ref_code.startswith("DPDP-")

        # All ERs linked to a requirement
        for er in ers:
            assert er.project_id == project.id
            assert er.requirement_id is not None


def test_generate_plan_idempotent(SessionTest):
    """Calling generate_plan twice does not create duplicate rows."""
    pack = load_pack("dpdp")
    with SessionTest() as db:
        client_row = Client(name="Idempotent Corp")
        db.add(client_row)
        db.flush()
        project = Project(client_id=client_row.id, service_type=ServiceType.dpdp, pack_id="dpdp")
        db.add(project)
        db.flush()

        s1 = generate_plan(db, project, pack)
        db.commit()
        s2 = generate_plan(db, project, pack)
        db.commit()

        assert s2.requirements_created == 0
        assert s2.evidence_requests_created == 0
        assert s2.tasks_created == 0
        # Total counts still correct
        assert db.query(Requirement).filter_by(project_id=project.id).count() == 12


def test_generate_vapt_plan(SessionTest):
    pack = load_pack("vapt")
    with SessionTest() as db:
        client_row = Client(name="Plan Test Corp VAPT")
        db.add(client_row)
        db.flush()
        project = Project(client_id=client_row.id, service_type=ServiceType.vapt, pack_id="vapt")
        db.add(project)
        db.flush()

        summary = generate_plan(db, project, pack)
        db.commit()

        assert summary.requirements_created == 12
        assert summary.evidence_requests_created == 11
        assert summary.tasks_created == 11


# ── API endpoint tests ────────────────────────────────────────────────────────

def test_api_list_packs(client):
    resp = client.get("/methodology/packs")
    assert resp.status_code == 200
    packs = resp.json()
    assert "dpdp" in packs
    assert "vapt" in packs


def test_api_get_pack(client):
    resp = client.get("/methodology/packs/dpdp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "dpdp"
    assert len(data["requirements"]) == 12


def test_api_generate_plan(client, SessionTest):
    # Create a project with pack_id set via PATCH
    c_resp = client.post("/clients/", json={"entity_name": "\1"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]
    client.patch(f"/projects/{pid}", json={"pack_id": "dpdp"})

    resp = client.post(f"/methodology/projects/{pid}/plan")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requirements_created"] == 12
    assert data["evidence_requests_created"] == 12
    assert data["tasks_created"] == 8

    # Second call is idempotent
    resp2 = client.post(f"/methodology/projects/{pid}/plan")
    assert resp2.status_code == 200
    assert resp2.json()["requirements_created"] == 0


def test_api_plan_no_pack_id(client):
    c_resp = client.post("/clients/", json={"entity_name": "\1"})
    cid = c_resp.json()["id"]
    p_resp = client.post("/projects/", json={"client_id": cid, "service_type": "dpdp"})
    pid = p_resp.json()["id"]

    resp = client.post(f"/methodology/projects/{pid}/plan")
    assert resp.status_code == 400
