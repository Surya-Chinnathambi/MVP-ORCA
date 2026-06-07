"""Gate tracker and QA agent endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.evidence import EvidenceItem, EvidenceRequest, EvidenceRequestStatus
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingStatus
from app.models.users import User
from app.schemas.gates import GateStatus, QAReportOut
from app.services.qa.agent import run_qa

router = APIRouter(prefix="/projects/{project_id}", tags=["gates"])

_ADVANCEABLE_GATES = {
    "G1_scope", "G2_evidence_requests", "G3_evidence_complete",
    "G4_findings", "G5_qa", "G6_report", "G7_closure",
}

_TERMINAL_STATUSES = {
    FindingStatus.approved.value,
    FindingStatus.remediated.value,
    FindingStatus.accepted.value,
}


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def _check_gate(gate: str, db: Session, project: Project) -> tuple[bool, str]:
    """Return (can_advance, reason_if_not)."""
    pid = project.id

    if gate == "G1_scope":
        approved = db.query(ScopeItem).filter_by(project_id=pid, approved=True).count()
        if approved == 0:
            return False, "No approved scope items. Approve at least one scope item first."
        return True, ""

    if gate == "G2_evidence_requests":
        open_count = (
            db.query(EvidenceRequest)
            .filter_by(project_id=pid, status=EvidenceRequestStatus.open)
            .count()
        )
        if open_count:
            return False, f"{open_count} evidence request(s) still open."
        return True, ""

    if gate == "G3_evidence_complete":
        open_count = (
            db.query(EvidenceRequest)
            .filter_by(project_id=pid, status=EvidenceRequestStatus.open)
            .count()
        )
        if open_count:
            return False, f"{open_count} evidence request(s) still open."
        item_count = db.query(EvidenceItem).filter_by(project_id=pid).count()
        if item_count == 0:
            return False, "No evidence items uploaded yet."
        return True, ""

    if gate == "G4_findings":
        findings = db.query(Finding).filter_by(project_id=pid).all()
        if not findings:
            return False, "No findings recorded for this project."
        blocked = [f.id for f in findings if f.status not in _TERMINAL_STATUSES]
        if blocked:
            return False, f"{len(blocked)} finding(s) not yet approved/remediated/accepted."
        return True, ""

    if gate == "G5_qa":
        # G5 requires no error-level QA issues
        gates = project.gates or {}
        if not gates.get("G4_findings"):
            return False, "G4 (findings approved) must be passed first."
        report = run_qa(db, project)
        if not report.passed:
            rules = [i.rule for i in report.issues if i.severity == "error"]
            return False, f"QA errors: {', '.join(rules)}"
        return True, ""

    if gate == "G6_report":
        gates = project.gates or {}
        if not gates.get("G5_qa"):
            return False, "G5 (QA complete) must be passed first."
        return True, ""

    if gate == "G7_closure":
        gates = project.gates or {}
        if not gates.get("G6_report"):
            return False, "G6 (report approved) must be passed first."
        return True, ""

    return False, f"Unknown gate '{gate}'."


@router.get("/gates/", response_model=GateStatus)
def get_gates(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db)
    return GateStatus(project_id=project_id, gates=project.gates or {})


@router.post("/gates/{gate}/advance", response_model=GateStatus)
def advance_gate(
    project_id: str,
    gate: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advance a gate if all prerequisites are met."""
    project = _project_or_404(project_id, db)

    if gate not in _ADVANCEABLE_GATES:
        raise HTTPException(status_code=400, detail=f"Unknown gate '{gate}'.")

    gates = dict(project.gates or {})
    if gates.get(gate):
        raise HTTPException(status_code=400, detail=f"Gate {gate} is already passed.")

    can, reason = _check_gate(gate, db, project)
    if not can:
        raise HTTPException(status_code=400, detail=reason)

    from app.services.audit import record_event
    gates[gate] = True
    project.gates = gates
    record_event(
        db,
        action=f"gate.advanced.{gate}",
        target_type="project",
        target_id=project_id,
        actor_id=current_user.id,
        project_id=project_id,
        before={gate: False},
        after={gate: True},
    )
    db.commit()
    db.refresh(project)
    return GateStatus(project_id=project_id, gates=project.gates)


@router.post("/qa/run", response_model=QAReportOut)
def run_qa_check(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run the deterministic QA agent against this project. Read-only."""
    project = _project_or_404(project_id, db)
    report = run_qa(db, project)
    return QAReportOut(**report.to_dict())
