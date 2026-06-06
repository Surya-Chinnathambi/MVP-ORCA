"""Stage C1 acceptance test — MVP DPDP+VAPT only.

Verifies:
- Only dpdp and vapt packs are discoverable via the loader.
- Both packs load and validate without errors.
- The 10 future packs are NOT in app/packs/ (they live in app/packs_future/).
- ServiceType enum still contains exactly dpdp and vapt.
- Existing projects can be created with dpdp or vapt service_type.
"""
from pathlib import Path

import pytest

from app.models.clients import ServiceType
from app.services.methodology.loader import available_packs, load_pack

PACKS_DIR = Path(__file__).parent.parent / "app" / "packs"
PACKS_FUTURE_DIR = Path(__file__).parent.parent / "app" / "packs_future"

FUTURE_PACK_KEYS = [
    "ai_governance",
    "cloud_posture",
    "cyber_strategy",
    "gdpr_gap",
    "grc_maturity",
    "incident_response",
    "iso_27001_readiness",
    "iso_27002_control_review",
    "iso_27701_privacy",
    "vendor_risk",
]


def test_only_mvp_packs_available():
    packs = available_packs()
    assert set(packs) == {"dpdp", "vapt"}, (
        f"Expected only dpdp and vapt in app/packs/, got: {packs}"
    )


def test_dpdp_pack_loads():
    pack = load_pack("dpdp")
    assert pack.key == "dpdp"
    assert len(pack.requirements) > 0


def test_vapt_pack_loads():
    pack = load_pack("vapt")
    assert pack.key == "vapt"
    assert len(pack.requirements) > 0


def test_future_packs_not_in_packs_dir():
    for key in FUTURE_PACK_KEYS:
        assert not (PACKS_DIR / key).exists(), (
            f"Future pack '{key}' should not be in app/packs/ — move it to app/packs_future/"
        )


def test_future_packs_in_packs_future_dir():
    assert PACKS_FUTURE_DIR.exists(), "app/packs_future/ directory must exist"
    for key in FUTURE_PACK_KEYS:
        assert (PACKS_FUTURE_DIR / key / "pack.json").exists(), (
            f"Future pack '{key}' missing from app/packs_future/"
        )


def test_future_pack_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_pack("iso_27001_readiness")


def test_service_type_enum_values():
    values = {e.value for e in ServiceType}
    assert values == {"dpdp", "vapt"}, f"ServiceType must have exactly dpdp+vapt, got: {values}"


def test_project_creation_dpdp(shared_session, tmp_path):
    from tests.conftest import make_client, make_org, make_project
    db, admin_id = shared_session
    org = make_org(db)
    client = make_client(db, org=org)
    project = make_project(db, client=client, owner_id=admin_id, service_type=ServiceType.dpdp)
    db.commit()
    assert project.service_type == ServiceType.dpdp.value


def test_project_creation_vapt(shared_session):
    from tests.conftest import make_client, make_org, make_project
    db, admin_id = shared_session
    org = make_org(db)
    client = make_client(db, org=org)
    project = make_project(db, client=client, owner_id=admin_id, service_type=ServiceType.vapt)
    db.commit()
    assert project.service_type == ServiceType.vapt.value
