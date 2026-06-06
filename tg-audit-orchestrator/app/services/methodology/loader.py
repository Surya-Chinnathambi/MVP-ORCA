"""Pack loader — reads and validates pack JSON against the canonical §7.1 schema."""
import json
from pathlib import Path
from typing import List

from pydantic import ValidationError

from app.services.packs.pack_schema import CanonicalPack

# Re-export CanonicalPack as Pack so existing callers keep working.
Pack = CanonicalPack

_PACKS_DIR = Path(__file__).parent.parent.parent / "packs"


def load_pack(pack_key: str) -> Pack:
    """Load and validate a pack by key (e.g. 'dpdp', 'vapt').

    Raises FileNotFoundError if the pack directory/file is missing.
    Raises ValueError with a clear field-level message if JSON is non-conformant.
    """
    path = _PACKS_DIR / pack_key / "pack.json"
    if not path.exists():
        raise FileNotFoundError(f"Pack not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        return Pack.model_validate(raw)
    except ValidationError as exc:
        missing = [
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        ]
        raise ValueError(
            f"Pack '{pack_key}' failed schema validation:\n" + "\n".join(f"  - {m}" for m in missing)
        ) from exc


def available_packs() -> List[str]:
    """Return keys of all available packs (directories containing pack.json)."""
    return [
        d.name
        for d in sorted(_PACKS_DIR.iterdir())
        if d.is_dir() and (d / "pack.json").exists()
    ]
