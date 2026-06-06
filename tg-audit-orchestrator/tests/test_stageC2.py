"""Stage C2 acceptance test — canonical pack schema, validated on load.

Verifies:
- CanonicalPack schema validates both MVP packs (dpdp, vapt) with zero errors.
- Loader rejects a deliberately broken pack fixture (missing qa_rules) with a clear message.
- MethodologyPack.version and .lifecycle are populated from JSON after register_pack().
"""
import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.methodology.loader import load_pack
from app.services.packs.pack_schema import CanonicalPack


# ── Schema validation ─────────────────────────────────────────────────────────

def test_dpdp_pack_validates_canonical_schema():
    pack = load_pack("dpdp")
    assert isinstance(pack, CanonicalPack)
    assert pack.version == "1.0.0"
    assert pack.lifecycle == "active"
    assert pack.service_description
    assert len(pack.role_responsibility_model) > 0
    assert len(pack.assessment_procedures) > 0
    assert len(pack.severity_model.high) > 0
    assert len(pack.review_gates) == 7
    assert len(pack.advisory_clinic_templates) >= 3


def test_vapt_pack_validates_canonical_schema():
    pack = load_pack("vapt")
    assert isinstance(pack, CanonicalPack)
    assert pack.version == "1.0.0"
    assert pack.lifecycle == "active"
    assert pack.service_description
    assert len(pack.role_responsibility_model) > 0
    assert len(pack.assessment_procedures) > 0
    assert pack.severity_model.critical
    assert len(pack.review_gates) == 7
    assert len(pack.advisory_clinic_templates) >= 1


def test_loader_rejects_pack_missing_qa_rules(tmp_path):
    broken = {
        "key": "broken",
        "title": "Broken Pack",
        "version": "0.1.0",
        "lifecycle": "draft",
        "service_description": "Test",
        "frameworks": [],
        "requirements": [
            {"ref_code": "B-01", "category": "test", "text": "Test requirement"}
        ]
        # qa_rules intentionally omitted
    }
    pack_dir = tmp_path / "broken"
    pack_dir.mkdir()
    (pack_dir / "pack.json").write_text(json.dumps(broken), encoding="utf-8")

    # Patch _PACKS_DIR to point to tmp_path for this test
    import app.services.methodology.loader as loader_mod
    original = loader_mod._PACKS_DIR
    loader_mod._PACKS_DIR = tmp_path
    try:
        with pytest.raises(ValueError) as exc_info:
            load_pack("broken")
        msg = str(exc_info.value)
        assert "qa_rules" in msg, f"Error should mention qa_rules, got: {msg}"
        assert "broken" in msg, f"Error should name the pack, got: {msg}"
    finally:
        loader_mod._PACKS_DIR = original


# ── Registry reads version/lifecycle from JSON ────────────────────────────────

def test_register_pack_reads_version_from_json(shared_session):
    from app.services.packs.registry import register_pack
    db, admin_id = shared_session
    mp = register_pack(db, "dpdp", actor_id=admin_id)
    db.commit()
    assert mp.version == "1.0.0", f"Expected version from JSON, got: {mp.version}"
    # DB lifecycle always starts at draft regardless of JSON lifecycle
    assert mp.lifecycle == "draft", f"DB lifecycle should be draft on registration, got: {mp.lifecycle}"


def test_register_pack_version_kwarg_overrides_json(shared_session):
    from app.services.packs.registry import register_pack
    db, admin_id = shared_session
    mp = register_pack(db, "vapt", version="2.0.0", actor_id=admin_id)
    db.commit()
    assert mp.version == "2.0.0"


def test_dpdp_pack_has_advisory_clinics():
    pack = load_pack("dpdp")
    categories = {c.category for c in pack.advisory_clinic_templates}
    expected = {
        "notice_and_consent",
        "rights_and_grievance",
        "breach_notification",
        "processor_governance",
        "retention_and_deletion",
        "security_safeguards",
    }
    assert expected == categories, f"Missing advisory clinic categories: {expected - categories}"
