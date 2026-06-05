"""PT-Orc adapter — reads a run directory and imports its contents into the ORM.

Usage (programmatic):
    from ptorc_adapter.importer import run_import
    result = run_import(db, project_id, Path("/path/to/run"))

Raises ValueError on validation errors (fail-loud by design).
"""
import json
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import Deliverable, DeliverableKind
from app.models.evidence import EvidenceItem
from app.models.scope import ScopeItem, ScopeItemKind
from app.models.tasks import Finding, FindingSource, FindingStatus
from app.services.audit import record_event, request_approval
from app.services.evidence.keyword_classify import classify_text
from ptorc_adapter.schemas import EvidenceRecord, FindingRecord, ReportBundle, ScopeImport

_DELIVERABLES_ROOT = Path("data/deliverables")


@dataclass
class ImportResult:
    project_id: str
    scope_items: List[str] = field(default_factory=list)
    scope_approvals: List[str] = field(default_factory=list)
    evidence_items: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    deliverable_id: str = ""


# ── File loaders (validate loudly) ────────────────────────────────────────────

def _load_scope(path: Path) -> ScopeImport:
    if not path.exists():
        raise FileNotFoundError(f"scope.json not found: {path}")
    try:
        return ScopeImport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise ValueError(f"scope.json validation error: {exc}") from exc


def _load_evidence(path: Path) -> List[EvidenceRecord]:
    if not path.exists():
        raise FileNotFoundError(f"evidence_manifest.jsonl not found: {path}")
    records: List[EvidenceRecord] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(EvidenceRecord.model_validate(json.loads(raw)))
        except Exception as exc:
            raise ValueError(f"evidence_manifest.jsonl line {i}: {exc}") from exc
    return records


def _load_findings(path: Path) -> List[FindingRecord]:
    if not path.exists():
        raise FileNotFoundError(f"findings.jsonl not found: {path}")
    records: List[FindingRecord] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(FindingRecord.model_validate(json.loads(raw)))
        except Exception as exc:
            raise ValueError(f"findings.jsonl line {i}: {exc}") from exc
    return records


def _load_report(path: Path) -> ReportBundle:
    if not path.exists():
        raise FileNotFoundError(f"report_bundle.json not found: {path}")
    try:
        return ReportBundle.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise ValueError(f"report_bundle.json validation error: {exc}") from exc


# ── Import steps ──────────────────────────────────────────────────────────────

def _import_scope(db: Session, project_id: str, scope: ScopeImport) -> tuple[list, list]:
    item_ids, approval_ids = [], []
    for target in scope.targets:
        item = ScopeItem(
            project_id=project_id,
            kind=ScopeItemKind.inclusion,
            value=target,
            approved=False,
        )
        db.add(item)
        db.flush()
        approval = request_approval(
            db,
            project_id=project_id,
            target_type="scope_item",
            target_id=item.id,
            reason=f"PT-Orc import: target '{target}' from {scope.engagement_profile} engagement",
            approver_role="reviewer",
            change_before=None,
            change_after={"kind": "inclusion", "value": target},
        )
        item_ids.append(item.id)
        approval_ids.append(approval.id)
    return item_ids, approval_ids


def _import_evidence(db: Session, project_id: str,
                     records: List[EvidenceRecord]) -> Dict[str, str]:
    """Returns mapping ptorc_id → orm EvidenceItem.id."""
    ev_map: Dict[str, str] = {}
    for rec in records:
        mime, _ = mimetypes.guess_type(rec.source_file)
        item = EvidenceItem(
            project_id=project_id,
            source_file=rec.source_file,
            sha256=rec.sha256,
            mime=mime or "application/octet-stream",
            reviewer_status="pending",
            classification=classify_text(rec.summary, filename=rec.source_file),
            extracted_text=rec.summary or None,
            item_metadata={"source": "ptorc", "phase": rec.phase, "ptorc_id": rec.id},
        )
        db.add(item)
        db.flush()
        ev_map[rec.id] = item.id
    return ev_map


def _import_findings(db: Session, project_id: str,
                     records: List[FindingRecord],
                     ev_map: Dict[str, str]) -> List[str]:
    finding_ids = []
    for rec in records:
        linked = [ev_map[eid] for eid in rec.evidence_ids if eid in ev_map]
        description = rec.description
        if rec.recommendation:
            description = f"{description}\n\nRecommendation: {rec.recommendation}".strip()
        finding = Finding(
            project_id=project_id,
            title=rec.title,
            severity=rec.severity,
            status=FindingStatus.in_review.value,
            source=FindingSource.ptorc.value,
            description=description or None,
            evidence_item_ids=linked,
        )
        db.add(finding)
        db.flush()
        record_event(
            db,
            action="finding.imported",
            target_type="finding",
            target_id=finding.id,
            project_id=project_id,
            after={"source": "ptorc", "phase": rec.phase, "severity": rec.severity},
        )
        finding_ids.append(finding.id)
    return finding_ids


def _import_report(db: Session, project_id: str,
                   report: ReportBundle, run_dir: Path) -> str:
    dest_dir = _DELIVERABLES_ROOT / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "report_bundle.json"
    shutil.copy2(run_dir / "report_bundle.json", dest)

    deliv = Deliverable(
        project_id=project_id,
        kind=DeliverableKind.report.value,
        format="ptorc",
        file_path=str(dest),
    )
    db.add(deliv)
    db.flush()
    return deliv.id


# ── Public entry point ─────────────────────────────────────────────────────────

def run_import(db: Session, project_id: str, run_dir: Path) -> ImportResult:
    """Import a PT-Orc run directory into the project.

    Validates all four files before writing any rows.
    Raises ValueError with file + line number on any schema error.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project '{project_id}' not found")

    run_dir = Path(run_dir)

    # Validate all files before touching the DB
    scope = _load_scope(run_dir / "scope.json")
    evidence_records = _load_evidence(run_dir / "evidence_manifest.jsonl")
    finding_records = _load_findings(run_dir / "findings.jsonl")
    report = _load_report(run_dir / "report_bundle.json")

    result = ImportResult(project_id=project_id)

    result.scope_items, result.scope_approvals = _import_scope(db, project_id, scope)
    ev_map = _import_evidence(db, project_id, evidence_records)
    result.evidence_items = list(ev_map.values())
    result.findings = _import_findings(db, project_id, finding_records, ev_map)
    result.deliverable_id = _import_report(db, project_id, report, run_dir)

    db.commit()
    return result
