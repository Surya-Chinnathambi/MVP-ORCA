"""Deterministic QA agent — driven by pack qa_rules, never mutates data."""
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.scope import Requirement
from app.models.tasks import Finding


@dataclass
class QAIssue:
    rule: str
    severity: str   # "error" | "warning"
    message: str
    item_ids: List[str] = field(default_factory=list)


@dataclass
class QAReport:
    project_id: str
    pack_id: Optional[str]
    rules_run: List[str]
    issues: List[QAIssue]

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "pack_id": self.pack_id,
            "rules_run": self.rules_run,
            "passed": self.passed,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity,
                    "message": i.message,
                    "item_ids": i.item_ids,
                }
                for i in self.issues
            ],
        }


# ── Individual rule checks ─────────────────────────────────────────────────

def _check_every_finding_has_evidence(db: Session, project_id: str) -> Optional[QAIssue]:
    without = [
        f.id for f in db.query(Finding).filter_by(project_id=project_id).all()
        if not f.evidence_item_ids
    ]
    if without:
        return QAIssue(
            rule="every_finding_has_evidence",
            severity="error",
            message=f"{len(without)} finding(s) have no evidence attached.",
            item_ids=without,
        )
    return None


def _check_open_evidence_requests_flagged(db: Session, project_id: str) -> Optional[QAIssue]:
    open_ers = [
        er.id for er in db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open)
        .all()
    ]
    if open_ers:
        return QAIssue(
            rule="open_evidence_requests_flagged",
            severity="warning",
            message=f"{len(open_ers)} evidence request(s) still open.",
            item_ids=open_ers,
        )
    return None


def _check_all_requirements_assessed(db: Session, project_id: str) -> Optional[QAIssue]:
    all_reqs = db.query(Requirement).filter_by(project_id=project_id).all()
    covered = {
        f.requirement_id
        for f in db.query(Finding).filter_by(project_id=project_id).all()
        if f.requirement_id
    }
    uncovered = [r.id for r in all_reqs if r.id not in covered]
    if uncovered:
        return QAIssue(
            rule="all_requirements_assessed",
            severity="warning",
            message=f"{len(uncovered)} requirement(s) have no linked findings.",
            item_ids=uncovered,
        )
    return None


def _check_severity_consistent(db: Session, project_id: str) -> Optional[QAIssue]:
    """Flag critical findings still in open status (no progression made)."""
    stale = [
        f.id for f in db.query(Finding)
        .filter_by(project_id=project_id, severity="critical", status="open")
        .all()
    ]
    if stale:
        return QAIssue(
            rule="severity_consistent",
            severity="warning",
            message=f"{len(stale)} critical finding(s) remain in 'open' status.",
            item_ids=stale,
        )
    return None


def _check_critical_findings_have_remediation(db: Session, project_id: str) -> Optional[QAIssue]:
    critical = db.query(Finding).filter_by(project_id=project_id, severity="critical").all()
    without_rem = []
    for f in critical:
        has = db.query(RemediationAction).filter_by(finding_id=f.id).count() > 0
        if not has:
            without_rem.append(f.id)
    if without_rem:
        return QAIssue(
            rule="critical_findings_have_remediation",
            severity="warning",
            message=f"{len(without_rem)} critical finding(s) have no remediation action.",
            item_ids=without_rem,
        )
    return None


def _check_evidence_lifecycle_ready(db: Session, project_id: str) -> Optional[QAIssue]:
    """Warn if accepted evidence items are not yet in 'classified' lifecycle state."""
    from app.models.evidence import EvidenceItem, EvidenceLifecycleState, ReviewerStatus
    not_classified = [
        i.id for i in db.query(EvidenceItem)
        .filter(
            EvidenceItem.project_id == project_id,
            EvidenceItem.reviewer_status == ReviewerStatus.accepted.value,
            EvidenceItem.internal_lifecycle_state.notin_([
                EvidenceLifecycleState.classified.value,
                EvidenceLifecycleState.packaged.value,
                EvidenceLifecycleState.delivered.value,
                EvidenceLifecycleState.archived.value,
            ]),
        ).all()
    ]
    if not_classified:
        return QAIssue(
            rule="evidence_lifecycle_ready",
            severity="warning",
            message=f"{len(not_classified)} accepted evidence item(s) not yet classified for release.",
            item_ids=not_classified,
        )
    return None


_RULE_HANDLERS = {
    "every_finding_has_evidence":       _check_every_finding_has_evidence,
    "open_evidence_requests_flagged":   _check_open_evidence_requests_flagged,
    "all_requirements_assessed":        _check_all_requirements_assessed,
    "severity_consistent":              _check_severity_consistent,
    "critical_findings_have_remediation": _check_critical_findings_have_remediation,
    "evidence_lifecycle_ready":         _check_evidence_lifecycle_ready,
}


# ── Public entry point ─────────────────────────────────────────────────────

def run_qa(db: Session, project: Project) -> QAReport:
    """Run all qa_rules from the project's pack (or all known rules if no pack).

    Returns a QAReport — does NOT modify any data.
    """
    from app.services.methodology.loader import load_pack

    rules_to_run: List[str] = list(_RULE_HANDLERS.keys())
    if project.pack_id:
        try:
            pack = load_pack(project.pack_id)
            rules_to_run = [r for r in pack.qa_rules if r in _RULE_HANDLERS]
        except Exception:
            pass

    issues: List[QAIssue] = []
    for rule in rules_to_run:
        handler = _RULE_HANDLERS[rule]
        issue = handler(db, project.id)
        if issue:
            issues.append(issue)

    return QAReport(
        project_id=project.id,
        pack_id=project.pack_id,
        rules_run=rules_to_run,
        issues=issues,
    )
