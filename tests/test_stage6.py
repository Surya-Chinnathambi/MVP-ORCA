"""Stage 6 acceptance test — evidence upload, extraction, link, manifest."""
import io
import json
import tempfile
from pathlib import Path

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
from app.models.evidence import EvidenceItem, EvidenceRequest, ReviewerStatus


# ── Helpers — create minimal fixture files without disk deps ──────────────────

def make_pdf_bytes(text: str = "Security policy and data breach notification procedures.") -> bytes:
    """Create a minimal valid PDF with embedded text using PyMuPDF."""
    import fitz  # type: ignore
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_png_bytes() -> bytes:
    """Create a tiny solid-colour PNG using Pillow."""
    from PIL import Image  # type: ignore
    img = Image.new("RGB", (64, 64), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
            email="admin@stage6.local",
            password_hash=hash_password("admin123"),
            full_name="Stage6 Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(Permission(user_id=admin.id, role_id=admin_role.id, scope_level="project"))

        client_row = Client(name="Stage6 Corp")
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
        c.post("/auth/login", json={"email": "admin@stage6.local", "password": "admin123"})
        yield c
    fastapi_app.dependency_overrides.clear()


# ── Upload + extraction ───────────────────────────────────────────────────────

def test_upload_pdf(client, seeded, tmp_path):
    pid = seeded["project_id"]
    pdf_data = make_pdf_bytes("Security policy and data breach notification procedures.")
    resp = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("policy.pdf", pdf_data, "application/pdf")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sha256"]
    assert len(data["sha256"]) == 64
    assert data["mime"] == "application/pdf"
    assert data["source_file"] == "policy.pdf"
    assert data["reviewer_status"] == "pending"
    # PDF has text — should be extracted
    assert data["extracted_text"] is not None
    assert len(data["extracted_text"]) > 10


def test_sha256_is_stable(client, seeded):
    """Re-uploading same file produces identical sha256."""
    pid = seeded["project_id"]
    pdf_data = make_pdf_bytes("Stable content.")
    resp1 = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("stable.pdf", pdf_data, "application/pdf")},
    )
    resp2 = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("stable.pdf", pdf_data, "application/pdf")},
    )
    assert resp1.json()["sha256"] == resp2.json()["sha256"]


def test_upload_png(client, seeded):
    pid = seeded["project_id"]
    png_data = make_png_bytes()
    resp = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("screenshot.png", png_data, "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sha256"]
    assert data["mime"] == "image/png"
    assert data["source_file"] == "screenshot.png"
    # extracted_text may be empty for plain-colour images without OCR


def test_upload_empty_file_rejected(client, seeded):
    pid = seeded["project_id"]
    resp = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


# ── Classification ────────────────────────────────────────────────────────────

def test_classification_keyword_match():
    from app.services.evidence.keyword_classify import classify_text
    cat = classify_text("The data breach notification was sent within 72 hours to the supervisory authority.")
    assert cat == "breach"


def test_classification_security():
    from app.services.evidence.keyword_classify import classify_text
    assert classify_text("Encryption and firewall configuration policy.") == "security"


def test_classification_fallback():
    from app.services.evidence.keyword_classify import classify_text
    assert classify_text("Random unrelated text with no keywords.") == "general"


# ── Link item to evidence request ─────────────────────────────────────────────

def test_link_item_to_er(client, seeded, SessionTest):
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid).first()
    er_id = er.id

    # Upload PDF linked to this ER
    pdf_data = make_pdf_bytes("Access control policy document.")
    upload_resp = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("access_control.pdf", pdf_data, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    item_id = upload_resp.json()["id"]
    assert upload_resp.json()["evidence_request_id"] is None  # not linked yet

    # Link it
    link_resp = client.post(
        f"/projects/{pid}/evidence-items/{item_id}/link",
        json={"evidence_request_id": er_id},
    )
    assert link_resp.status_code == 200
    assert link_resp.json()["evidence_request_id"] == er_id

    # Verify in DB
    with SessionTest() as db:
        item = db.get(EvidenceItem, item_id)
    assert item.evidence_request_id == er_id


def test_upload_with_er_attached_directly(client, seeded, SessionTest):
    """Upload with evidence_request_id query param sets the link immediately."""
    pid = seeded["project_id"]
    with SessionTest() as db:
        er = db.query(EvidenceRequest).filter_by(project_id=pid).first()

    pdf_data = make_pdf_bytes("Data protection officer appointment letter.")
    resp = client.post(
        f"/projects/{pid}/evidence-items/upload?evidence_request_id={er.id}",
        files={"file": ("dpo_letter.pdf", pdf_data, "application/pdf")},
    )
    assert resp.status_code == 201
    assert resp.json()["evidence_request_id"] == er.id


# ── Reviewer workflow ─────────────────────────────────────────────────────────

def test_accept_item(client, seeded, SessionTest):
    pid = seeded["project_id"]
    pdf_data = make_pdf_bytes("Risk assessment report.")
    item_id = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("risk.pdf", pdf_data, "application/pdf")},
    ).json()["id"]

    resp = client.post(
        f"/projects/{pid}/evidence-items/{item_id}/review",
        json={"accepted": True, "reason": "Verified accurate"},
    )
    assert resp.status_code == 200
    assert resp.json()["reviewer_status"] == "accepted"

    with SessionTest() as db:
        item = db.get(EvidenceItem, item_id)
    assert item.reviewer_status == ReviewerStatus.accepted


def test_reject_item_requires_approval(client, seeded, SessionTest):
    pid = seeded["project_id"]
    pdf_data = make_pdf_bytes("Incomplete audit evidence.")
    item_id = client.post(
        f"/projects/{pid}/evidence-items/upload",
        files={"file": ("incomplete.pdf", pdf_data, "application/pdf")},
    ).json()["id"]

    resp = client.post(
        f"/projects/{pid}/evidence-items/{item_id}/review",
        json={"accepted": False, "reason": "Document is outdated"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["target_type"] == "evidence_rejection"
    assert data["target_id"] == item_id

    # Item still pending — approval not yet decided
    with SessionTest() as db:
        item = db.get(EvidenceItem, item_id)
    assert item.reviewer_status == ReviewerStatus.pending

    approval_id = data["id"]

    # Approve the rejection
    decide = client.post(f"/approvals/{approval_id}/decide", json={
        "approved": True,
        "reason": "Confirmed outdated — rejecting",
    })
    assert decide.status_code == 200
    assert decide.json()["status"] == "approved"

    # Item is now rejected
    with SessionTest() as db:
        item = db.get(EvidenceItem, item_id)
    assert item.reviewer_status == ReviewerStatus.rejected


# ── Manifest ──────────────────────────────────────────────────────────────────

def test_manifest_has_all_items(client, seeded, SessionTest):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/evidence-items/manifest/jsonl")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 2  # at least the PDF and PNG uploaded earlier
    # Check required fields in each record
    for rec in records:
        assert "id" in rec
        assert "sha256" in rec
        assert "source_file" in rec
        assert "reviewer_status" in rec
        assert len(rec["sha256"]) == 64


def test_manifest_file_written_on_disk(seeded):
    """The manifest.jsonl file must exist on disk after uploads."""
    from app.services.evidence.manifest import manifest_path
    pid = seeded["project_id"]
    path = manifest_path(pid)
    assert path.exists()
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(lines) >= 2
    # Each line must be valid JSON
    for line in lines:
        rec = json.loads(line)
        assert "sha256" in rec


# ── List + filter ─────────────────────────────────────────────────────────────

def test_list_evidence_items(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/evidence-items/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_filter_by_reviewer_status(client, seeded):
    pid = seeded["project_id"]
    resp = client.get(f"/projects/{pid}/evidence-items/?reviewer_status=pending")
    assert resp.status_code == 200
    assert all(i["reviewer_status"] == "pending" for i in resp.json())
