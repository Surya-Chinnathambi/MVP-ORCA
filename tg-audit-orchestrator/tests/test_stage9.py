"""Stage 9 acceptance test — PT-Orc adapter."""
import json
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services.auth import hash_password

import app.models  # noqa: F401
from app.models.users import Role, RoleName, User
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import Deliverable
from app.models.evidence import EvidenceItem
from app.models.scope import ScopeItem
from app.models.tasks import Finding
from app.models.workflow import ApprovalRequest, ApprovalStatus

from ptorc_adapter.importer import run_import
from ptorc_adapter.schemas import FindingRecord, ScopeImport


# ── DB fixtures ───────────────────────────────────────────────────────────────

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
def project_id(engine, SessionTest):
    with Session(engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        client_row = Client(entity_name="Stage9 Corp")
        db.add(client_row)
        db.flush()
        project = Project(
            client_id=client_row.id,
            service_type=ServiceType.vapt,
            pack_id="vapt",
            gates={
                "G1_scope": False, "G2_evidence_requests": False,
                "G3_evidence_complete": False, "G4_findings": False,
                "G5_qa": False, "G6_report": False, "G7_closure": False,
            },
        )
        db.add(project)
        db.commit()
        yield project.id


# ── Run-dir fixture factory ───────────────────────────────────────────────────

def _make_run_dir(tmp_path: Path, project_ref: str, *, bad_finding_line: bool = False) -> Path:
    run_dir = tmp_path / "ptorc_run"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "scope.json").write_text(json.dumps({
        "project_ref": project_ref,
        "engagement_profile": "external",
        "testing_depth": "standard",
        "auth_level": "none",
        "targets": ["example.com", "api.example.com"],
        "rules_of_engagement": "No DoS, business hours only",
        "window": {"start": "2026-06-01", "end": "2026-06-14"},
    }), encoding="utf-8")

    evidence_lines = [
        json.dumps({"id": "ev-001", "phase": "01_dns",
                    "source_file": "dns.txt", "sha256": "a" * 64,
                    "summary": "DNS records for example.com"}),
        json.dumps({"id": "ev-002", "phase": "04_tls",
                    "source_file": "tls_scan.txt", "sha256": "b" * 64,
                    "summary": "TLS 1.0 still enabled on port 443"}),
    ]
    (run_dir / "evidence_manifest.jsonl").write_text(
        "\n".join(evidence_lines), encoding="utf-8"
    )

    if bad_finding_line:
        findings_lines = [
            json.dumps({"id": "f-001", "title": "TLS 1.0 enabled",
                        "severity": "medium", "phase": "04_tls",
                        "evidence_ids": ["ev-002"],
                        "description": "TLS 1.0 is deprecated.",
                        "recommendation": "Disable TLS 1.0."}),
            '{"id": "f-bad", "title": "Missing severity"}',   # no severity field
        ]
    else:
        findings_lines = [
            json.dumps({"id": "f-001", "title": "TLS 1.0 enabled",
                        "severity": "medium", "phase": "04_tls",
                        "evidence_ids": ["ev-002"],
                        "description": "TLS 1.0 is deprecated.",
                        "recommendation": "Disable TLS 1.0."}),
            json.dumps({"id": "f-002", "title": "SQL Injection in search",
                        "severity": "high", "phase": "05_web",
                        "evidence_ids": ["ev-001"],
                        "description": "Unsanitised user input.",
                        "recommendation": "Use parameterised queries."}),
        ]
    (run_dir / "findings.jsonl").write_text(
        "\n".join(findings_lines), encoding="utf-8"
    )

    (run_dir / "report_bundle.json").write_text(json.dumps({
        "project_ref": project_ref,
        "profile": "external",
        "retest_status": "scheduled",
        "residual_risk": "Medium — 2 high-severity findings unresolved",
        "counts": {"findings": 2, "evidence": 2},
    }), encoding="utf-8")

    return run_dir


# ── Happy-path import ─────────────────────────────────────────────────────────

def test_import_scope_items_unapproved(engine, project_id, tmp_path, SessionTest):
    run_dir = _make_run_dir(tmp_path, project_id)
    with Session(engine) as db:
        result = run_import(db, project_id, run_dir)

    assert len(result.scope_items) == 2
    with Session(engine) as db:
        for sid in result.scope_items:
            item = db.get(ScopeItem, sid)
            assert item is not None
            assert item.approved is False   # must NOT be auto-approved
            assert item.kind == "inclusion"


def test_import_scope_approvals_created(engine, project_id, SessionTest):
    with Session(engine) as db:
        items = db.query(ScopeItem).filter_by(project_id=project_id).all()
    assert len(items) >= 2  # from the import above

    with Session(engine) as db:
        for item in items:
            approvals = (
                db.query(ApprovalRequest)
                .filter_by(project_id=project_id, target_type="scope_item", target_id=item.id)
                .all()
            )
            assert len(approvals) >= 1
            assert approvals[0].status == ApprovalStatus.pending


def test_import_evidence_items_ptorc_source(engine, project_id, SessionTest):
    with Session(engine) as db:
        items = db.query(EvidenceItem).filter_by(project_id=project_id).all()
    assert len(items) == 2
    for item in items:
        meta = item.item_metadata or {}
        assert meta.get("source") == "ptorc"
        assert meta.get("phase") is not None
        assert len(item.sha256) == 64


def test_import_findings_in_review(engine, project_id, SessionTest):
    with Session(engine) as db:
        findings = db.query(Finding).filter_by(project_id=project_id).all()
    assert len(findings) == 2
    for f in findings:
        assert f.source == "ptorc"
        assert f.status == "in_review"


def test_import_finding_evidence_links(engine, project_id, SessionTest):
    """Each finding's evidence_item_ids should reference our ORM item IDs, not PT-Orc IDs."""
    with Session(engine) as db:
        findings = db.query(Finding).filter_by(project_id=project_id).all()
        ev_ids = {i.id for i in db.query(EvidenceItem).filter_by(project_id=project_id).all()}

    for f in findings:
        for linked_id in (f.evidence_item_ids or []):
            assert linked_id in ev_ids, f"Linked ID {linked_id} is not an ORM EvidenceItem.id"


def test_import_deliverable_created(engine, project_id, SessionTest):
    with Session(engine) as db:
        deliverables = db.query(Deliverable).filter_by(
            project_id=project_id, format="ptorc"
        ).all()
    assert len(deliverables) == 1
    assert deliverables[0].kind == "report"
    assert deliverables[0].file_path is not None
    assert Path(deliverables[0].file_path).exists()


# ── Schema validation (fail-loud) ─────────────────────────────────────────────

def test_malformed_finding_rejected(engine, project_id, tmp_path, SessionTest):
    """A malformed findings.jsonl line must raise ValueError with line number."""
    run_dir = _make_run_dir(tmp_path / "bad", project_id, bad_finding_line=True)
    with Session(engine) as db:
        with pytest.raises(ValueError) as exc_info:
            run_import(db, project_id, run_dir)
        err = str(exc_info.value)
        assert "findings.jsonl" in err
        assert "line 2" in err


def test_invalid_severity_rejected():
    """FindingRecord rejects unknown severity at schema level."""
    with pytest.raises(Exception):
        FindingRecord.model_validate({
            "id": "f-x", "title": "Test", "severity": "catastrophic",
            "phase": "01_dns",
        })


def test_missing_scope_field_rejected(tmp_path):
    """scope.json missing required field raises ValueError."""
    bad_dir = tmp_path / "missing_scope"
    bad_dir.mkdir()
    (bad_dir / "scope.json").write_text(
        json.dumps({"project_ref": "x", "engagement_profile": "external"}),
        encoding="utf-8",
    )
    from ptorc_adapter.importer import _load_scope
    with pytest.raises(ValueError, match="scope.json"):
        _load_scope(bad_dir / "scope.json")


def test_missing_file_raises_file_not_found(tmp_path, engine, project_id):
    """Missing evidence_manifest.jsonl raises FileNotFoundError."""
    bad_dir = tmp_path / "missing_evidence"
    bad_dir.mkdir()
    (bad_dir / "scope.json").write_text(json.dumps({
        "project_ref": project_id,
        "engagement_profile": "internal",
        "testing_depth": "deep",
        "auth_level": "admin",
        "targets": ["10.0.0.1"],
    }), encoding="utf-8")
    # No evidence_manifest.jsonl
    with Session(engine) as db:
        with pytest.raises(FileNotFoundError, match="evidence_manifest.jsonl"):
            run_import(db, project_id, bad_dir)


def test_nonexistent_project_raises(tmp_path, engine):
    """Importing into a non-existent project raises ValueError."""
    run_dir = _make_run_dir(tmp_path / "noproject", "00000000-0000-0000-0000-000000000000")
    with Session(engine) as db:
        with pytest.raises(ValueError, match="not found"):
            run_import(db, "00000000-0000-0000-0000-000000000000", run_dir)


# ── Schemas ───────────────────────────────────────────────────────────────────

def test_scope_schema_parses():
    s = ScopeImport.model_validate({
        "project_ref": "abc",
        "engagement_profile": "external",
        "testing_depth": "standard",
        "auth_level": "none",
        "targets": ["example.com"],
    })
    assert s.targets == ["example.com"]
    assert s.rules_of_engagement == ""
