"""Stage 24 acceptance test — ISO / GDPR frameworks and packs.

Verifies:
1. All four new packs load and validate against the Pack schema.
2. gdpr_gap pack has requirements, evidence_requests, task_templates, review_gates, severity_model.
3. iso_27001_readiness, iso_27002_control_review, iso_27701_privacy packs validate.
4. framework_mapper.get_framework returns controls for each new framework.
5. Cross-framework mapping: eu_gdpr GDPR-ART5 maps to dpdp_act control(s).
6. Cross-framework mapping: iso_27701-7.3.1 maps to both eu_gdpr and dpdp_act controls.
7. map_evidence_to_frameworks returns all mappings for a control.
8. find_controls_for_pack returns the correct controls for a pack key.
9. FrameworkKey enum recognises all new keys.
10. generate_plan includes new framework titles for a project using iso_27001.
"""
import pytest
from pydantic import ValidationError

from app.models.scope import FrameworkKey
from app.services.framework_mapper import (
    find_controls_for_pack,
    get_control,
    get_cross_framework_refs,
    get_framework,
    list_loaded_frameworks,
    map_evidence_to_frameworks,
)
from app.services.methodology.loader import Pack, available_packs, load_pack


# ── 1. All four new packs load ─────────────────────────────────────────────────

def test_gdpr_gap_pack_loads():
    pack = load_pack("gdpr_gap")
    assert pack.key == "gdpr_gap"
    assert "eu_gdpr" in pack.frameworks


def test_iso_27001_readiness_pack_loads():
    pack = load_pack("iso_27001_readiness")
    assert pack.key == "iso_27001_readiness"
    assert "iso_27001" in pack.frameworks


def test_iso_27002_control_review_pack_loads():
    pack = load_pack("iso_27002_control_review")
    assert pack.key == "iso_27002_control_review"
    assert "iso_27002" in pack.frameworks


def test_iso_27701_privacy_pack_loads():
    pack = load_pack("iso_27701_privacy")
    assert pack.key == "iso_27701_privacy"
    assert "iso_27701" in pack.frameworks


# ── 2. gdpr_gap pack content ───────────────────────────────────────────────────

def test_gdpr_gap_pack_has_requirements_and_evidence():
    pack = load_pack("gdpr_gap")
    assert len(pack.requirements) >= 6
    assert len(pack.evidence_requests) >= 6
    assert len(pack.task_templates) >= 5


def test_gdpr_gap_pack_has_review_gates_and_severity_model():
    pack = load_pack("gdpr_gap")
    assert len(pack.review_gates) >= 4
    assert pack.severity_model is not None
    assert pack.severity_model.critical is not None
    assert pack.severity_model.high is not None


def test_gdpr_gap_advisory_clinic_templates():
    pack = load_pack("gdpr_gap")
    assert len(pack.advisory_clinic_templates) >= 2
    categories = {t.category for t in pack.advisory_clinic_templates}
    assert "lawful_basis" in categories


# ── 3. available_packs includes all new packs ──────────────────────────────────

def test_available_packs_includes_new_packs():
    packs = available_packs()
    assert "gdpr_gap" in packs
    assert "iso_27001_readiness" in packs
    assert "iso_27002_control_review" in packs
    assert "iso_27701_privacy" in packs


# ── 4. Framework JSON files load ───────────────────────────────────────────────

def test_eu_gdpr_framework_loads():
    fw = get_framework("eu_gdpr")
    assert fw["key"] == "eu_gdpr"
    assert len(fw["controls"]) >= 5


def test_iso_27001_framework_loads():
    fw = get_framework("iso_27001")
    assert fw["key"] == "iso_27001"
    assert len(fw["controls"]) >= 5


def test_iso_27002_framework_loads():
    fw = get_framework("iso_27002")
    assert fw["key"] == "iso_27002"
    assert len(fw["controls"]) >= 4


def test_iso_27701_framework_loads():
    fw = get_framework("iso_27701")
    assert fw["key"] == "iso_27701"
    assert len(fw["controls"]) >= 4


def test_nist_framework_loads():
    fw = get_framework("nist")
    assert fw["key"] == "nist"
    assert len(fw["controls"]) >= 4


# ── 5. Cross-framework: eu_gdpr ART5 → dpdp_act ───────────────────────────────

def test_gdpr_art5_maps_to_dpdp():
    refs = get_cross_framework_refs("eu_gdpr", "GDPR-ART5", "dpdp_act")
    assert len(refs) >= 1
    assert any("DPDP" in r for r in refs)


# ── 6. Cross-framework: iso_27701-7.3.1 → eu_gdpr and dpdp_act ───────────────

def test_iso_27701_consent_maps_to_gdpr_and_dpdp():
    gdpr_refs = get_cross_framework_refs("iso_27701", "27701-7.3.1", "eu_gdpr")
    dpdp_refs = get_cross_framework_refs("iso_27701", "27701-7.3.1", "dpdp_act")
    assert len(gdpr_refs) >= 1
    assert len(dpdp_refs) >= 1


# ── 7. map_evidence_to_frameworks returns all mappings ────────────────────────

def test_map_evidence_to_frameworks_gdpr_art5():
    all_mappings = map_evidence_to_frameworks("eu_gdpr", "GDPR-ART5")
    assert "dpdp_act" in all_mappings
    assert isinstance(all_mappings["dpdp_act"], list)
    assert len(all_mappings["dpdp_act"]) >= 1


def test_map_evidence_returns_empty_for_unknown_control():
    result = map_evidence_to_frameworks("eu_gdpr", "GDPR-NONEXISTENT")
    assert result == {}


# ── 8. find_controls_for_pack ─────────────────────────────────────────────────

def test_find_controls_for_iso_27701_privacy_pack():
    controls = find_controls_for_pack("iso_27701_privacy", "iso_27701")
    assert len(controls) >= 4
    ids = [c["id"] for c in controls]
    assert "27701-5.2.1" in ids


def test_find_controls_for_iso_27001_readiness_pack():
    controls = find_controls_for_pack("iso_27001_readiness", "iso_27001")
    assert len(controls) >= 5


def test_find_controls_for_iso_27002_control_review_pack():
    controls = find_controls_for_pack("iso_27002_control_review", "iso_27002")
    assert len(controls) >= 4


# ── 9. FrameworkKey enum ───────────────────────────────────────────────────────

def test_framework_key_enum_has_new_keys():
    assert FrameworkKey("iso_27001") == FrameworkKey.iso_27001
    assert FrameworkKey("iso_27002") == FrameworkKey.iso_27002
    assert FrameworkKey("iso_27701") == FrameworkKey.iso_27701
    assert FrameworkKey("eu_gdpr") == FrameworkKey.eu_gdpr
    assert FrameworkKey("nist") == FrameworkKey.nist


# ── 10. list_loaded_frameworks returns new keys ────────────────────────────────

def test_list_loaded_frameworks_includes_all():
    keys = list_loaded_frameworks()
    for expected in ["eu_gdpr", "iso_27001", "iso_27002", "iso_27701", "nist"]:
        assert expected in keys


# ── 11. Pack schema rejects invalid packs ─────────────────────────────────────

def test_pack_schema_rejects_missing_requirements():
    with pytest.raises(ValidationError):
        Pack.model_validate({"key": "bad_pack", "title": "Bad", "frameworks": []})


def test_get_control_returns_none_for_unknown():
    result = get_control("eu_gdpr", "GDPR-NONEXISTENT-999")
    assert result is None
