"""Plan generator — creates Requirement, EvidenceRequest, and Task rows from a pack."""
from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from app.models.clients import Project
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.scope import Framework, FrameworkKey, Requirement
from app.models.tasks import Task, TaskKind
from app.services.methodology.loader import Pack


@dataclass
class PlanSummary:
    requirements_created: int
    evidence_requests_created: int
    tasks_created: int


def generate_plan(db: Session, project: Project, pack: Pack) -> PlanSummary:
    """Idempotently populate a project with requirements, evidence requests,
    and tasks derived from the given pack.

    Already-existing rows (matched by ref_code for requirements, title for tasks)
    are skipped so the function is safe to call multiple times.
    """
    # ── 1. Upsert Framework rows for this pack ────────────────────────────────
    fw_id_by_key: dict[str, str] = {}
    for fw_key in pack.frameworks:
        if fw_key not in FrameworkKey.__members__:
            continue  # unknown framework key — skip gracefully
        fw = db.query(Framework).filter_by(key=fw_key).first()
        if fw is None:
            fw = Framework(
                key=fw_key,
                title=_framework_title(fw_key),
                version="1.0",
            )
            db.add(fw)
            db.flush()
        fw_id_by_key[fw_key] = fw.id

    # Pick the first known framework as the default for requirements
    default_fw_id = next(iter(fw_id_by_key.values()), None)

    # ── 2. Upsert Requirements ────────────────────────────────────────────────
    existing_refs = {
        r.ref_code
        for r in db.query(Requirement).filter_by(project_id=project.id).all()
    }
    req_id_by_ref: dict[str, str] = {
        r.ref_code: r.id
        for r in db.query(Requirement).filter_by(project_id=project.id).all()
    }
    reqs_created = 0
    for pr in pack.requirements:
        if pr.ref_code in existing_refs:
            continue
        req = Requirement(
            framework_id=default_fw_id,
            project_id=project.id,
            ref_code=pr.ref_code,
            text=pr.text,
            evidence_expectation=pr.evidence_expectation,
            category=pr.category,
        )
        db.add(req)
        db.flush()
        req_id_by_ref[pr.ref_code] = req.id
        reqs_created += 1

    # ── 3. Upsert Evidence Requests ───────────────────────────────────────────
    existing_er_titles = {
        er.title
        for er in db.query(EvidenceRequest).filter_by(project_id=project.id).all()
    }
    ers_created = 0
    for ert in pack.evidence_requests:
        if ert.title in existing_er_titles:
            continue
        req_id = req_id_by_ref.get(ert.requirement_ref)
        er = EvidenceRequest(
            project_id=project.id,
            requirement_id=req_id,
            title=ert.title,
            description=ert.description,
            status=EvidenceRequestStatus.open,
        )
        db.add(er)
        ers_created += 1

    # ── 4. Upsert Tasks ───────────────────────────────────────────────────────
    existing_task_titles = {
        t.title
        for t in db.query(Task).filter_by(project_id=project.id).all()
    }
    tasks_created = 0
    for tt in pack.task_templates:
        if tt.title in existing_task_titles:
            continue
        kind = tt.kind if tt.kind in TaskKind.__members__ else TaskKind.review.value
        task = Task(
            project_id=project.id,
            kind=kind,
            title=tt.title,
            status="open",
        )
        db.add(task)
        tasks_created += 1

    db.flush()
    return PlanSummary(
        requirements_created=reqs_created,
        evidence_requests_created=ers_created,
        tasks_created=tasks_created,
    )


def _framework_title(key: str) -> str:
    _titles = {
        "dpdp_act":   "Digital Personal Data Protection Act 2023",
        "owasp_wstg": "OWASP Web Security Testing Guide v4.2",
        "owasp_asvs": "OWASP Application Security Verification Standard v4",
        "owasp_api10":"OWASP API Security Top 10 (2023)",
        "ptes":       "Penetration Testing Execution Standard v1.1",
    }
    return _titles.get(key, key)
