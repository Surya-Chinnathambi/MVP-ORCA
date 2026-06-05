"""PT-Orc adapter v2 — reads a run directory and imports its contents into the ORM.

v2 behaviour:
- Incremental import: a second import for the same project_id + run_id updates
  existing findings' retest_status instead of duplicating rows.
- Superseded evidence: duplicate sha256 on retest creates a new EvidenceItem that
  supersedes the old one via the Stage 18 supersede chain.
- Correlation: findings whose evidence_ids overlap an existing finding in the same
  project are linked to that finding (retest_status update) rather than duplicated.
  Never auto-merges across projects.
- Offensive narrative: pack_scoped_data from FindingRecord is stored on the Finding's
  pack_scoped_data column — never in title, description, or recommendation.
- Imported findings land source=ptorc, status=in_review — never auto-approved.
- Imported scope items require approval before going live.

Usage:
    from ptorc_adapter.importer import run_import
    result = run_import(db, project_id, Path("/path/to/run"), run_id="run-001")
"""
import json
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

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
    run_id: str
    scope_items: List[str] = field(default_factory=list)
    scope_approvals: List[str] = field(default_factory=list)
    evidence_items: List[str] = field(default_factory=list)
    findings_created: List[str] = field(default_factory=list)
    findings_updated: List[str] = field(default_factory=list)
    deliverable_id: str = ""

    @property
    def findings(self) -> List[str]:
        return self.findings_created + self.findings_updated


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


def _import_evidence(
    db: Session,
    project_id: str,
    records: List[EvidenceRecord],
    is_retest: bool,
) -> Dict[str, str]:
    """Return mapping ptorc_id → orm EvidenceItem.id.

    On retest: if sha256 already exists in this project, supersede the old item.
    """
    existing_by_sha: Dict[str, str] = {
        item.sha256: item.id
        for item in db.query(EvidenceItem).filter_by(project_id=project_id).all()
        if item.sha256
    }
    ev_map: Dict[str, str] = {}
    for rec in records:
        mime, _ = mimetypes.guess_type(rec.source_file)
        # Always supersede when sha256 already exists in this project (retest or fresh)
        old_id: Optional[str] = existing_by_sha.get(rec.sha256)

        item = EvidenceItem(
            project_id=project_id,
            source_file=rec.source_file,
            sha256=rec.sha256,
            mime=mime or "application/octet-stream",
            reviewer_status="pending",
            classification=classify_text(rec.summary, filename=rec.source_file),
            extracted_text=rec.summary or None,
            item_metadata={"source": "ptorc", "phase": rec.phase, "ptorc_id": rec.id},
            supersedes_id=old_id,
        )
        db.add(item)
        db.flush()
        ev_map[rec.id] = item.id
    return ev_map


def _find_correlated(
    db: Session,
    project_id: str,
    evidence_orm_ids: List[str],
) -> Optional[Finding]:
    """Return an existing ptorc Finding in this project whose evidence_item_ids
    overlap with evidence_orm_ids or their superseded predecessors.
    Returns None if not found or overlap is empty.
    """
    if not evidence_orm_ids:
        return None
    # Expand to include superseded IDs so retest evidence links back to original findings
    ev_set = set(evidence_orm_ids)
    for item_id in list(ev_set):
        item = db.get(EvidenceItem, item_id)
        if item and item.supersedes_id:
            ev_set.add(item.supersedes_id)

    candidates = (
        db.query(Finding)
        .filter_by(project_id=project_id, source=FindingSource.ptorc.value)
        .all()
    )
    for finding in candidates:
        existing_ids = set(finding.evidence_item_ids or [])
        if existing_ids & ev_set:
            return finding
    return None


def _import_findings(
    db: Session,
    project_id: str,
    records: List[FindingRecord],
    ev_map: Dict[str, str],
    run_id: str,
) -> tuple[List[str], List[str]]:
    """Return (created_ids, updated_ids).

    - New finding: create with status=in_review, source=ptorc.
    - Correlated finding (evidence overlap): update retest_status, pack_scoped_data.
    - Offensive narrative: stored only in pack_scoped_data, not in title/description.
    """
    created_ids: List[str] = []
    updated_ids: List[str] = []

    for rec in records:
        linked = [ev_map[eid] for eid in rec.evidence_ids if eid in ev_map]
        offensive_data = rec.extract_offensive_narrative()

        correlated = _find_correlated(db, project_id, linked)
        if correlated is not None:
            correlated.retest_status = rec.retest_status
            if offensive_data:
                existing = dict(correlated.pack_scoped_data or {})
                existing.update(offensive_data)
                correlated.pack_scoped_data = existing
            db.flush()
            record_event(
                db,
                action="finding.retest_updated",
                target_type="finding",
                target_id=correlated.id,
                project_id=project_id,
                after={
                    "source": "ptorc",
                    "phase": rec.phase,
                    "retest_status": rec.retest_status,
                    "run_id": run_id,
                },
            )
            updated_ids.append(correlated.id)
        else:
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
                retest_status=rec.retest_status,
                phase_tag=rec.phase,
                ptorc_run_id=run_id,
                pack_scoped_data=offensive_data if offensive_data else None,
            )
            db.add(finding)
            db.flush()
            record_event(
                db,
                action="finding.imported",
                target_type="finding",
                target_id=finding.id,
                project_id=project_id,
                after={
                    "source": "ptorc",
                    "phase": rec.phase,
                    "severity": rec.severity,
                    "run_id": run_id,
                },
            )
            created_ids.append(finding.id)

    return created_ids, updated_ids


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

def run_import(
    db: Session,
    project_id: str,
    run_dir: Path,
    run_id: Optional[str] = None,
) -> ImportResult:
    """Import a PT-Orc v2 run directory into the project.

    run_id identifies this run. If run_id already has findings in this project,
    the import operates in retest mode: updates findings' retest_status instead of
    creating duplicates; supersedes evidence where sha256 matches.

    Validates all four files before writing any rows.
    Raises ValueError with file + line number on any schema error.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project '{project_id}' not found")

    run_dir = Path(run_dir)
    if run_id is None:
        run_id = run_dir.name

    # Validate all files before touching DB
    scope = _load_scope(run_dir / "scope.json")
    evidence_records = _load_evidence(run_dir / "evidence_manifest.jsonl")
    finding_records = _load_findings(run_dir / "findings.jsonl")
    report = _load_report(run_dir / "report_bundle.json")

    # Detect retest mode: does this project already have findings from this run_id?
    is_retest = (
        db.query(Finding)
        .filter_by(project_id=project_id, ptorc_run_id=run_id, source=FindingSource.ptorc.value)
        .first()
    ) is not None

    result = ImportResult(project_id=project_id, run_id=run_id)

    if not is_retest:
        result.scope_items, result.scope_approvals = _import_scope(db, project_id, scope)

    ev_map = _import_evidence(db, project_id, evidence_records, is_retest=is_retest)
    result.evidence_items = list(ev_map.values())

    result.findings_created, result.findings_updated = _import_findings(
        db, project_id, finding_records, ev_map, run_id
    )
    result.deliverable_id = _import_report(db, project_id, report, run_dir)

    db.commit()
    return result
