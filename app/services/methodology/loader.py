"""Pack loader — reads and validates pack JSON against the frozen Pack schema."""
import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ValidationError

# ── Frozen pack schema ────────────────────────────────────────────────────────

class IntakeQuestion(BaseModel):
    id: str
    text: str


class ScopeTemplate(BaseModel):
    kind: str
    prompt: str


class PackRequirement(BaseModel):
    ref_code: str
    category: str
    text: str
    evidence_expectation: Optional[str] = None


class EvidenceRequestTemplate(BaseModel):
    requirement_ref: str
    title: str
    description: Optional[str] = None


class TaskTemplate(BaseModel):
    kind: str
    title: str


class FindingTemplate(BaseModel):
    category: str
    title_pattern: str


class SeverityModel(BaseModel):
    critical: Optional[str] = None
    high: Optional[str] = None
    medium: Optional[str] = None
    low: Optional[str] = None
    informational: Optional[str] = None


class ReviewGate(BaseModel):
    id: str
    label: str
    required_role: Optional[str] = None


class AdvisoryClinicTemplate(BaseModel):
    category: str
    title: str
    guidance: Optional[str] = None


class Pack(BaseModel):
    key: str
    title: str
    frameworks: List[str]
    intake_questions: List[IntakeQuestion] = []
    scope_template: List[ScopeTemplate] = []
    requirements: List[PackRequirement]
    evidence_requests: List[EvidenceRequestTemplate] = []
    task_templates: List[TaskTemplate] = []
    finding_templates: List[FindingTemplate] = []
    report_templates: List[str] = []
    qa_rules: List[str] = []
    approval_triggers: List[str] = []
    # Phase 2 extensions (Stage 24)
    severity_model: Optional[SeverityModel] = None
    review_gates: List[ReviewGate] = []
    advisory_clinic_templates: List[AdvisoryClinicTemplate] = []


# ── Loader ────────────────────────────────────────────────────────────────────

_PACKS_DIR = Path(__file__).parent.parent.parent / "packs"


def load_pack(pack_key: str) -> Pack:
    """Load and validate a pack by key (e.g. 'dpdp', 'vapt').

    Raises FileNotFoundError if the pack directory/file is missing.
    Raises ValidationError (Pydantic) if the JSON does not match the schema.
    """
    path = _PACKS_DIR / pack_key / "pack.json"
    if not path.exists():
        raise FileNotFoundError(f"Pack not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Pack.model_validate(raw)


def available_packs() -> List[str]:
    """Return keys of all available packs (directories containing pack.json)."""
    return [
        d.name
        for d in sorted(_PACKS_DIR.iterdir())
        if d.is_dir() and (d / "pack.json").exists()
    ]
