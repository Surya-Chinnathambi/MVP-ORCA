"""Load framework JSON files and resolve cross-framework control mappings."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_FRAMEWORKS_DIR = Path(__file__).parent.parent / "frameworks"


@lru_cache(maxsize=None)
def _load_framework(key: str) -> dict:
    path = _FRAMEWORKS_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"Framework file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_framework(key: str) -> dict:
    """Return the full framework dict for *key* (e.g. 'eu_gdpr')."""
    return _load_framework(key)


def get_control(framework_key: str, control_id: str) -> Optional[dict]:
    """Return a single control dict or None if not found."""
    fw = get_framework(framework_key)
    for control in fw.get("controls", []):
        if control["id"] == control_id:
            return control
    return None


def get_cross_framework_refs(
    source_framework: str,
    source_control_id: str,
    target_framework: str,
) -> list[str]:
    """Return the list of target-framework control IDs that the given source control maps to."""
    control = get_control(source_framework, source_control_id)
    if control is None:
        return []
    refs: dict = control.get("cross_framework_refs", {})
    return refs.get(target_framework, [])


def map_evidence_to_frameworks(
    source_framework: str,
    source_control_id: str,
) -> dict[str, list[str]]:
    """Return all cross-framework mappings for a given source control.

    Returns a dict of {target_framework_key: [control_ids]}.
    """
    control = get_control(source_framework, source_control_id)
    if control is None:
        return {}
    return dict(control.get("cross_framework_refs", {}))


def find_controls_for_pack(pack_key: str, framework_key: str) -> list[dict]:
    """Return framework controls whose applicable_packs include *pack_key*."""
    fw = get_framework(framework_key)
    return [
        c for c in fw.get("controls", [])
        if pack_key in c.get("applicable_packs", [])
    ]


def list_loaded_frameworks() -> list[str]:
    """Return keys of all framework JSON files present on disk."""
    return sorted(p.stem for p in _FRAMEWORKS_DIR.glob("*.json"))
