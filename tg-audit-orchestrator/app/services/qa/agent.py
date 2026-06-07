"""Deterministic QA agent — driven by pack qa_rules, never mutates data.

Rules per vapt.md Step 10 (7 required rules):
  every_finding_has_evidence  — each finding has ≥1 accepted evidence item
  severity_consistent         — critical/high findings are not stuck in draft
  evidence_requests_resolved  — all evidence requests are received or waived
  requirements_covered        — every requirement has at least one linked finding
  remediation_has_owner       — findings at remediation_planned+ have a RemediationAction with owner
  scope_finding_match         — no finding references a phase outside the approved scope
  no_draft_findings           — no findings remain at draft at report time
"""
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.scope import Requirement
from app.models.tasks import Finding, FindingStatus


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


# ── Rule implementations ───────────────────────────────────────────────────

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


def _check_severity_consistent(db: Session, project_id: str) -> Optional[QAIssue]:
    """Critical and high findings that are still in draft state haven't been reviewed."""
    stale = [
        f.id for f in db.query(Finding)
        .filter(
            Finding.project_id == project_id,
            Finding.severity.in_(["critical", "high"]),
            Finding.status == FindingStatus.draft.value,
        ).all()
    ]
    if stale:
        return QAIssue(
            rule="severity_consistent",
            severity="warning",
            message=f"{len(stale)} critical/high finding(s) still in draft — review required.",
            item_ids=stale,
        )
    return None


def _check_evidence_requests_resolved(db: Session, project_id: str) -> Optional[QAIssue]:
    """All evidence requests must be received or waived (not still open)."""
    open_ers = [
        er.id for er in db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open)
        .all()
    ]
    if open_ers:
        return QAIssue(
            rule="evidence_requests_resolved",
            severity="warning",
            message=f"{len(open_ers)} evidence request(s) still open (not received or waived).",
            item_ids=open_ers,
        )
    return None


def _check_requirements_covered(db: Session, project_id: str) -> Optional[QAIssue]:
    """Every requirement must have at least one linked finding."""
    all_reqs = db.query(Requirement).filter_by(project_id=project_id).all()
    covered = {
        f.requirement_id
        for f in db.query(Finding).filter_by(project_id=project_id).all()
        if f.requirement_id
    }
    uncovered = [r.id for r in all_reqs if r.id not in covered]
    if uncovered:
        return QAIssue(
            rule="requirements_covered",
            severity="warning",
            message=f"{len(uncovered)} requirement(s) have no linked findings.",
            item_ids=uncovered,
        )
    return None


def _check_remediation_has_owner(db: Session, project_id: str) -> Optional[QAIssue]:
    """Findings at remediation_planned or later must have a RemediationAction with an owner."""
    _REMEDIATION_STATUSES = {
        FindingStatus.remediation_planned.value,
        FindingStatus.retest_pending.value,
        FindingStatus.closed.value,
        FindingStatus.risk_accepted.value,
    }
    findings_needing_rem = db.query(Finding).filter(
        Finding.project_id == project_id,
        Finding.status.in_(list(_REMEDIATION_STATUSES)),
    ).all()
    without_owner = []
    for f in findings_needing_rem:
        rem = db.query(RemediationAction).filter_by(
            finding_id=f.id
        ).filter(RemediationAction.owner_id.isnot(None)).first()
        if rem is None:
            without_owner.append(f.id)
    if without_owner:
        return QAIssue(
            rule="remediation_has_owner",
            severity="error",
            message=f"{len(without_owner)} finding(s) in remediation stage have no owned RemediationAction.",
            item_ids=without_owner,
        )
    return None


def _check_scope_finding_match(db: Session, project_id: str) -> Optional[QAIssue]:
    """No finding should reference a PT-Orc phase that implies out-of-scope testing.

    This checks that imported findings have phase_tags matching known PT-Orc phases.
    Unknown/malformed phase tags indicate a scope boundary issue.
    """
    from ptorc_adapter.schemas import _VALID_PHASES
    bad = [
        f.id for f in db.query(Finding).filter_by(project_id=project_id).all()
        if f.phase_tag and f.phase_tag not in _VALID_PHASES
    ]
    if bad:
        return QAIssue(
            rule="scope_finding_match",
            severity="warning",
            message=f"{len(bad)} finding(s) have unrecognised phase tags — verify scope boundary.",
            item_ids=bad,
        )
    return None


def _check_no_draft_findings(db: Session, project_id: str) -> Optional[QAIssue]:
    """No findings should remain in draft state at report time."""
    drafts = [
        f.id for f in db.query(Finding)
        .filter_by(project_id=project_id, status=FindingStatus.draft.value)
        .all()
    ]
    if drafts:
        return QAIssue(
            rule="no_draft_findings",
            severity="error",
            message=f"{len(drafts)} finding(s) still in draft — must be reviewed before report.",
            item_ids=drafts,
        )
    return None


_RULE_HANDLERS = {
    "every_finding_has_evidence":   _check_every_finding_has_evidence,
    "severity_consistent":          _check_severity_consistent,
    "evidence_requests_resolved":   _check_evidence_requests_resolved,
    "requirements_covered":         _check_requirements_covered,
    "remediation_has_owner":        _check_remediation_has_owner,
    "scope_finding_match":          _check_scope_finding_match,
    "no_draft_findings":            _check_no_draft_findings,
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
