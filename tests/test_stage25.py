"""Stage 25 acceptance test — remaining methodology packs.

Verifies:
1. All 6 new packs load and validate against the Pack schema.
2. Each new pack has requirements, evidence_requests, task_templates, review_gates.
3. vendor_risk produces its full evidence-request set (5 ERs).
4. generate_plan creates requirements, ERs, and tasks for vendor_risk.
5. generate_plan creates requirements, ERs, and tasks for grc_maturity.
6. isaca and tg_baseline framework files load with correct controls.
7. FrameworkKey enum recognises isaca and tg_baseline.
8. Advisory clinic templates present for each new pack.
9. No new pack injects offensive primitives into EngagementCore (file-level grep).
10. No new pack JSON contains opsec|c2|killchain|exploit_phase symbols.
"""
import re
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.scope import FrameworkKey
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password
from app.services.framework_mapper import (
    find_controls_for_pack,
    get_framework,
    list_loaded_frameworks,
)
from app.services.methodology.loader import available_packs, load_pack
from app.services.methodology.plan import generate_plan

_NEW_PACK_KEYS = [
    "grc_maturity",
    "vendor_risk",
    "incident_response",
    "cyber_strategy",
    "cloud_posture",
    "ai_governance",
]

_PACKS_DIR = Path(__file__).parent.parent / "app" / "packs"
_ENGAGEMENTCORE_DIR = Path(__file__).parent.parent / "app" / "engagementcore"
_OFFENSIVE_PATTERN = re.compile(r"\b(opsec|c2|killchain|exploit_phase)\b", re.IGNORECASE)


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
def seeded_project(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()

    client = Client(entity_name="TestCo", organization_id=org.id)
    db.add(client)
    db.flush()

    project = Project(
        client_id=client.id,
        service_type=ServiceType.vapt,
        status="active",
    )
    db.add(project)
    db.flush()
    return project


# ── 1. All 6 new packs load ────────────────────────────────────────────────────

@pytest.mark.parametrize("pack_key", _NEW_PACK_KEYS)
def test_new_pack_loads(pack_key):
    pack = load_pack(pack_key)
    assert pack.key == pack_key


# ── 2. Each new pack has core content ─────────────────────────────────────────

@pytest.mark.parametrize("pack_key", _NEW_PACK_KEYS)
def test_new_pack_has_required_content(pack_key):
    pack = load_pack(pack_key)
    assert len(pack.requirements) >= 5
    assert len(pack.evidence_requests) >= 5
    assert len(pack.task_templates) >= 5
    assert len(pack.review_gates) >= 4
    assert pack.severity_model is not None


# ── 3. vendor_risk produces full evidence-request set ─────────────────────────

def test_vendor_risk_evidence_requests():
    pack = load_pack("vendor_risk")
    assert len(pack.evidence_requests) == 5
    refs = {er.requirement_ref for er in pack.evidence_requests}
    assert "VR-POLICY-01" in refs
    assert "VR-INVENTORY-01" in refs
    assert "VR-ASSESS-01" in refs
    assert "VR-CONTRACT-01" in refs
    assert "VR-MONITOR-01" in refs


def test_vendor_risk_has_advisory_clinic_templates():
    pack = load_pack("vendor_risk")
    assert len(pack.advisory_clinic_templates) >= 2
    categories = {t.category for t in pack.advisory_clinic_templates}
    assert "due_diligence" in categories


# ── 4. generate_plan for vendor_risk ──────────────────────────────────────────

def test_generate_plan_vendor_risk(db: Session, seeded_project: Project):
    pack = load_pack("vendor_risk")
    summary = generate_plan(db, seeded_project, pack)
    assert summary.requirements_created == 5
    assert summary.evidence_requests_created == 5
    assert summary.tasks_created >= 5


def test_generate_plan_vendor_risk_idempotent(db: Session, seeded_project: Project):
    pack = load_pack("vendor_risk")
    summary2 = generate_plan(db, seeded_project, pack)
    assert summary2.requirements_created == 0
    assert summary2.evidence_requests_created == 0
    assert summary2.tasks_created == 0


# ── 5. generate_plan for grc_maturity ─────────────────────────────────────────

def test_generate_plan_grc_maturity(db: Session, engine):
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    org = Organization(name="GRC Org")
    session.add(org)
    session.flush()

    client = Client(entity_name="GRC Corp", organization_id=org.id)
    session.add(client)
    session.flush()

    project = Project(
        client_id=client.id,
        service_type=ServiceType.vapt,
        status="active",
    )
    session.add(project)
    session.flush()

    pack = load_pack("grc_maturity")
    summary = generate_plan(session, project, pack)
    assert summary.requirements_created == 5
    assert summary.evidence_requests_created == 5
    assert summary.tasks_created >= 7
    session.close()


# ── 6. New framework files load ────────────────────────────────────────────────

def test_isaca_framework_loads():
    fw = get_framework("isaca")
    assert fw["key"] == "isaca"
    assert len(fw["controls"]) >= 4


def test_tg_baseline_framework_loads():
    fw = get_framework("tg_baseline")
    assert fw["key"] == "tg_baseline"
    assert len(fw["controls"]) >= 5


def test_list_loaded_frameworks_includes_new():
    keys = list_loaded_frameworks()
    assert "isaca" in keys
    assert "tg_baseline" in keys


# ── 7. FrameworkKey enum has new values ───────────────────────────────────────

def test_framework_key_enum_isaca():
    assert FrameworkKey("isaca") == FrameworkKey.isaca


def test_framework_key_enum_tg_baseline():
    assert FrameworkKey("tg_baseline") == FrameworkKey.tg_baseline


# ── 8. Advisory clinic templates present for all new packs ────────────────────

@pytest.mark.parametrize("pack_key", _NEW_PACK_KEYS)
def test_advisory_clinic_templates_present(pack_key):
    pack = load_pack(pack_key)
    assert len(pack.advisory_clinic_templates) >= 2


# ── 9. No offensive primitives injected into EngagementCore ───────────────────

def test_no_offensive_symbols_in_engagementcore():
    if not _ENGAGEMENTCORE_DIR.exists():
        pytest.skip("engagementcore directory not present")
    violations = []
    for path in _ENGAGEMENTCORE_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _OFFENSIVE_PATTERN.search(text):
            violations.append(str(path))
    assert violations == [], f"Offensive primitives found in EngagementCore: {violations}"


# ── 10. No offensive symbols in any new pack JSON ─────────────────────────────

@pytest.mark.parametrize("pack_key", _NEW_PACK_KEYS)
def test_no_offensive_symbols_in_pack_json(pack_key):
    pack_path = _PACKS_DIR / pack_key / "pack.json"
    text = pack_path.read_text(encoding="utf-8")
    match = _OFFENSIVE_PATTERN.search(text)
    assert match is None, (
        f"Offensive symbol '{match.group()}' found in {pack_key}/pack.json"
    )


# ── 11. available_packs includes all new packs ────────────────────────────────

def test_available_packs_has_all_stage25():
    packs = available_packs()
    for key in _NEW_PACK_KEYS:
        assert key in packs, f"Pack '{key}' missing from available_packs()"


# ── 12. Pack schema rejects pack without requirements ─────────────────────────

def test_pack_schema_still_rejects_missing_requirements():
    from app.services.methodology.loader import Pack
    with pytest.raises(ValidationError):
        Pack.model_validate({"key": "bad", "title": "Bad Pack", "frameworks": []})
