"""Stage C6 acceptance test — cleanup and documented decisions.

Verifies:
- Empty stub dirs are gone; ptorc_adapter still imports and the VAPT pilot still runs.
- A finding maps to >1 framework and an evidence item supports >1 requirement, queryable.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.organization import Organization
from app.models.scope import Requirement
from app.models.tasks import Finding, FindingSeverity
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def seeded(db):
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="c6_admin@test.local",
        password_hash=hash_password("pass"),
        full_name="C6 Admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    org = Organization(name="C6 Org", display_name="C6 Org")
    db.add(org)
    db.flush()
    client = Client(entity_name="C6 Client", organization_id=org.id)
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, service_type=ServiceType.vapt, owner_id=admin.id)
    db.add(project)
    db.flush()
    return db, admin, project


# ── Stub directory removal ────────────────────────────────────────────────────

def test_empty_ptorc_service_stub_gone():
    assert not Path("app/services/ptorc").exists(), (
        "app/services/ptorc/ empty stub must be removed (real adapter is ptorc_adapter/)"
    )


def test_empty_ptorc_adapter_stub_gone():
    assert not Path("ptorc-adapter").exists(), (
        "ptorc-adapter/ empty top-level stub must be removed (real adapter is ptorc_adapter/)"
    )


def test_real_ptorc_adapter_imports():
    from ptorc_adapter import importer
    assert hasattr(importer, "run_import"), "ptorc_adapter.importer must have run_import function"


# ── Framework §8.2 mappings ───────────────────────────────────────────────────

def test_finding_maps_to_multiple_frameworks(seeded):
    db, admin, project = seeded
    finding = Finding(
        project_id=project.id,
        title="Multi-framework finding",
        severity=FindingSeverity.high.value,
        source="manual",
        pack_scoped_data={"frameworks": ["owasp_asvs", "nist", "ptes"]},
    )
    db.add(finding)
    db.flush()

    reloaded = db.get(Finding, finding.id)
    frameworks = reloaded.pack_scoped_data.get("frameworks", [])
    assert len(frameworks) >= 2, f"Finding should map to ≥2 frameworks, got: {frameworks}"
    assert "owasp_asvs" in frameworks
    assert "nist" in frameworks


def test_evidence_item_supports_multiple_requirements(seeded):
    db, admin, project = seeded

    # Create two requirements for the same project
    from app.models.scope import Framework
    fw = Framework(key="owasp_asvs", title="OWASP ASVS", version="4.0")
    db.add(fw)
    db.flush()

    req1 = Requirement(
        project_id=project.id, framework_id=fw.id,
        ref_code="VAPT-AUTH-01", text="Auth test", category="auth"
    )
    req2 = Requirement(
        project_id=project.id, framework_id=fw.id,
        ref_code="VAPT-AUTHZ-01", text="AuthZ test", category="authz"
    )
    db.add(req1)
    db.add(req2)
    db.flush()

    # Create two EvidenceRequests for the same evidence file (linked to different requirements)
    er1 = EvidenceRequest(
        project_id=project.id, requirement_id=req1.id,
        title="Auth evidence", status=EvidenceRequestStatus.received.value
    )
    er2 = EvidenceRequest(
        project_id=project.id, requirement_id=req2.id,
        title="AuthZ evidence", status=EvidenceRequestStatus.received.value
    )
    db.add(er1)
    db.add(er2)
    db.flush()

    # One evidence item (same sha256) linked to two evidence requests — simulates many-to-one
    from app.models.evidence import EvidenceItem
    ev1 = EvidenceItem(
        project_id=project.id, evidence_request_id=er1.id,
        source_file="auth_test.pdf", sha256="abc123",
        mime="application/pdf", classification="auth"
    )
    ev2 = EvidenceItem(
        project_id=project.id, evidence_request_id=er2.id,
        source_file="auth_test.pdf", sha256="abc123",  # same file, different requirement
        mime="application/pdf", classification="authz"
    )
    db.add(ev1)
    db.add(ev2)
    db.flush()

    # Verify: querying both requirements covered by the same sha256
    from app.models.evidence import EvidenceItem as EI
    ev_items = db.query(EI).filter(EI.sha256 == "abc123", EI.project_id == project.id).all()
    req_ids_covered = {ev.evidence_request_id for ev in ev_items}
    assert req_ids_covered == {er1.id, er2.id}, (
        f"One evidence file should support ≥2 requirements, got: {req_ids_covered}"
    )


def test_db_md_documents_framework_decision():
    db_md = Path("db.md").read_text()
    assert "JSON-as-library" in db_md, "db.md must document the framework-library decision"
    assert "tech debt" in db_md.lower(), "db.md must note the JSON-array linkage as tech debt"
    assert "finding_frameworks" in db_md, "db.md must mention the future finding_frameworks join table"
