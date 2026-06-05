"""Stage 26 acceptance test — PT-Orc import v2.

Verifies:
1. Import an ai_llm profile fixture run; findings land in_review with correct phase tags.
2. Retest import: findings update retest_status, no duplicates created.
3. Evidence supersede chain: retest with same sha256 creates new item with supersedes_id.
4. Malformed v2 line in findings.jsonl is rejected with a clear ValueError.
5. Invalid engagement_profile in scope.json is rejected.
6. Invalid phase tag is rejected at schema validation.
7. Offensive narrative fields stored in pack_scoped_data, never in title/description.
8. Correlated finding (evidence overlap) gets retest_status update, not a new row.
9. scope.json validation rejects unknown engagement_profile.
10. Imported scope items require approval (approved=False).
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.tasks import Finding, FindingSource, FindingStatus
from app.models.evidence import EvidenceItem
from app.models.scope import ScopeItem
from ptorc_adapter.importer import run_import
from ptorc_adapter.schemas import (
    FindingRecord,
    EvidenceRecord,
    ScopeImport,
    ReportBundle,
)


# ── DB fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    return e


@pytest.fixture(scope="module")
def db(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def project(db: Session):
    org = Organization(name="PT Org v2")
    db.add(org)
    db.flush()
    client = Client(name="PT Client", organization_id=org.id)
    db.add(client)
    db.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.vapt,
        status="active",
    )
    db.add(proj)
    db.flush()
    return proj


# ── Run-dir builder helpers ────────────────────────────────────────────────────

def _write_run_dir(
    tmp: Path,
    *,
    profile: str = "ai_llm",
    targets: list = None,
    evidence_lines: list = None,
    finding_lines: list = None,
    report_extra: dict = None,
    run_id: str = None,  # ignored — kept for call-site compatibility
) -> Path:
    run = tmp
    run.mkdir(parents=True, exist_ok=True)

    scope = {
        "project_ref": "test",
        "engagement_profile": profile,
        "testing_depth": "full",
        "auth_level": "authenticated",
        "targets": targets or ["https://api.example.com/llm"],
        "rules_of_engagement": "no production data",
    }
    (run / "scope.json").write_text(json.dumps(scope))

    ev_lines = evidence_lines or [
        json.dumps({
            "id": "ev-01", "phase": "09_ai_llm",
            "source_file": "prompt_injection_proof.txt",
            "sha256": "aaa111", "summary": "prompt injection evidence",
        })
    ]
    (run / "evidence_manifest.jsonl").write_text("\n".join(ev_lines))

    f_lines = finding_lines or [
        json.dumps({
            "id": "f-01", "title": "Prompt Injection", "severity": "high",
            "phase": "09_ai_llm", "evidence_ids": ["ev-01"],
            "description": "LLM prompt injection found",
            "recommendation": "Sanitise inputs",
            "retest_status": "n/a",
        })
    ]
    (run / "findings.jsonl").write_text("\n".join(f_lines))

    report = {
        "project_ref": "test",
        "profile": profile,
        "retest_status": "n/a",
        "residual_risk": "",
        "counts": {"high": 1},
    }
    if report_extra:
        report.update(report_extra)
    (run / "report_bundle.json").write_text(json.dumps(report))

    return run


# ── 1. ai_llm profile import ───────────────────────────────────────────────────

def test_ai_llm_import_findings_land_in_review(db: Session, project: Project, tmp_path):
    run_dir = _write_run_dir(tmp_path)
    result = run_import(db, project.id, run_dir, run_id="run-ai-001")

    assert len(result.findings_created) == 1
    finding_id = result.findings_created[0]
    finding = db.get(Finding, finding_id)
    assert finding.status == FindingStatus.in_review.value
    assert finding.source == FindingSource.ptorc.value
    assert finding.phase_tag == "09_ai_llm"
    assert finding.ptorc_run_id == "run-ai-001"


def test_ai_llm_import_scope_requires_approval(db: Session, project: Project):
    items = (
        db.query(ScopeItem)
        .filter_by(project_id=project.id)
        .all()
    )
    assert len(items) >= 1
    assert all(not item.approved for item in items)


# ── 2. Retest import updates retest_status, no duplicates ─────────────────────

def test_retest_import_no_duplicate_findings(db: Session, project: Project, tmp_path):
    retest_dir = _write_run_dir(
        tmp_path / "retest",
        finding_lines=[
            json.dumps({
                "id": "f-01", "title": "Prompt Injection", "severity": "high",
                "phase": "09_ai_llm", "evidence_ids": ["ev-01"],
                "description": "LLM prompt injection found",
                "recommendation": "Sanitise inputs",
                "retest_status": "passed",
            })
        ],
    )
    result = run_import(db, project.id, retest_dir, run_id="run-ai-001")

    assert len(result.findings_created) == 0
    assert len(result.findings_updated) == 1

    finding = db.get(Finding, result.findings_updated[0])
    assert finding.retest_status == "passed"

    total = (
        db.query(Finding)
        .filter_by(project_id=project.id, ptorc_run_id="run-ai-001")
        .count()
    )
    assert total == 1


# ── 3. Evidence supersede chain on retest ─────────────────────────────────────

def test_retest_evidence_supersedes_old_item(db: Session, project: Project, tmp_path):
    retest_dir = _write_run_dir(tmp_path / "retest2")
    result = run_import(db, project.id, retest_dir, run_id="run-ai-002")

    new_item_id = result.evidence_items[0]
    new_item = db.get(EvidenceItem, new_item_id)
    assert new_item.supersedes_id is not None


# ── 4. Malformed findings.jsonl line rejected ──────────────────────────────────

def test_malformed_findings_line_rejected(db: Session, project: Project, tmp_path):
    bad_dir = _write_run_dir(
        tmp_path / "bad",
        finding_lines=[
            json.dumps({"id": "f-bad", "severity": "unknown_severity",
                        "phase": "09_ai_llm", "title": "Bad"}),
        ],
    )
    with pytest.raises(ValueError, match="findings.jsonl line 1"):
        run_import(db, project.id, bad_dir, run_id="run-bad-001")


# ── 5. Invalid engagement_profile rejected ────────────────────────────────────

def test_invalid_profile_rejected(db: Session, project: Project, tmp_path):
    bad_dir = _write_run_dir(tmp_path / "badprofile", profile="unknown_profile")
    with pytest.raises(ValueError, match="scope.json"):
        run_import(db, project.id, bad_dir, run_id="run-badprofile-001")


# ── 6. Invalid phase tag rejected ─────────────────────────────────────────────

def test_invalid_phase_tag_rejected():
    with pytest.raises(Exception):
        EvidenceRecord.model_validate({
            "id": "ev-x", "phase": "99_hacking",
            "source_file": "x.txt", "sha256": "abc",
        })


# ── 7. Offensive narrative stored in pack_scoped_data only ────────────────────

def test_offensive_narrative_quarantined_in_pack_scoped_data(db: Session, project: Project, tmp_path):
    offensive_dir = _write_run_dir(
        tmp_path / "offensive",
        finding_lines=[
            json.dumps({
                "id": "f-off", "title": "SSRF Finding", "severity": "medium",
                "phase": "08_app_api", "evidence_ids": [],
                "description": "SSRF in API endpoint",
                "recommendation": "Validate URLs",
                "retest_status": "n/a",
                "pack_scoped_data": {
                    "attack_chain": "step1→step2",
                    "c2_config": "beacon config here",
                    "opsec_notes": "avoid EDR",
                },
            })
        ],
    )
    result = run_import(db, project.id, offensive_dir, run_id="run-off-001")
    finding_id = result.findings_created[0]
    finding = db.get(Finding, finding_id)

    assert "attack_chain" not in (finding.description or "")
    assert "c2_config" not in (finding.title or "")
    assert finding.pack_scoped_data is not None
    assert "attack_chain" in finding.pack_scoped_data
    assert "c2_config" in finding.pack_scoped_data
    assert "opsec_notes" in finding.pack_scoped_data


# ── 8. Correlated finding (evidence overlap) gets retest update ───────────────

def test_correlated_finding_retest_update(db: Session, project: Project, tmp_path):
    # First import creates finding linked to ev-corr
    first_dir = _write_run_dir(
        tmp_path / "corr1",
        evidence_lines=[
            json.dumps({
                "id": "ev-corr", "phase": "08_app_api",
                "source_file": "ssrf_proof.txt", "sha256": "corr999",
                "summary": "SSRF evidence",
            })
        ],
        finding_lines=[
            json.dumps({
                "id": "f-corr", "title": "SSRF", "severity": "high",
                "phase": "08_app_api", "evidence_ids": ["ev-corr"],
                "description": "SSRF via API", "recommendation": "Filter",
                "retest_status": "n/a",
            })
        ],
    )
    result1 = run_import(db, project.id, first_dir, run_id="run-corr-001")
    assert len(result1.findings_created) == 1
    original_finding_id = result1.findings_created[0]

    # Second import: different run_id, same evidence sha256 → evidence overlaps → correlation
    second_dir = _write_run_dir(
        tmp_path / "corr2",
        evidence_lines=[
            json.dumps({
                "id": "ev-corr2", "phase": "08_app_api",
                "source_file": "ssrf_proof.txt", "sha256": "corr999",
                "summary": "SSRF retest evidence",
            })
        ],
        finding_lines=[
            json.dumps({
                "id": "f-corr2", "title": "SSRF retest", "severity": "high",
                "phase": "08_app_api", "evidence_ids": ["ev-corr2"],
                "description": "SSRF retest", "recommendation": "Filter",
                "retest_status": "passed",
            })
        ],
    )
    result2 = run_import(db, project.id, second_dir, run_id="run-corr-002")

    assert len(result2.findings_updated) == 1
    assert result2.findings_updated[0] == original_finding_id
    updated = db.get(Finding, original_finding_id)
    assert updated.retest_status == "passed"


# ── 9. Schema: ReportBundle rejects unknown profile ───────────────────────────

def test_report_bundle_rejects_unknown_profile():
    with pytest.raises(Exception):
        ReportBundle.model_validate({
            "project_ref": "x", "profile": "unknown_profile",
        })


# ── 10. Schema: ScopeImport validates known profiles ─────────────────────────

def test_scope_import_valid_profiles():
    for profile in ["external", "internal", "web", "api", "ai_llm", "cloud", "ad", "hybrid"]:
        s = ScopeImport.model_validate({
            "project_ref": "x", "engagement_profile": profile,
            "testing_depth": "full", "auth_level": "none",
            "targets": ["target"],
        })
        assert s.engagement_profile == profile
