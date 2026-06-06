"""Web views — Deliverables builder and remediation tracker."""
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Client, Project
from app.models.delivery import Deliverable, RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest
from app.models.tasks import Finding, FindingSeverity, Task
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_web_user

router = APIRouter(tags=["web-deliverables"])
templates = Jinja2Templates(directory="app/web/templates")

_BASE_DATA = Path("data/deliverables")


@router.get("/projects/{project_id}/report", response_class=HTMLResponse)
def report_view(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    client = db.get(Client, project.client_id)

    from app.models.scan import ScanJob
    from app.models.scope import Requirement, ScopeItem

    findings = (
        db.query(Finding).filter_by(project_id=project_id)
        .order_by(Finding.created_at.desc()).all()
    )
    tasks = db.query(Task).filter_by(project_id=project_id).all()
    ev_items = db.query(EvidenceItem).filter_by(project_id=project_id).all()
    ev_requests = db.query(EvidenceRequest).filter_by(project_id=project_id).all()
    scan_jobs = (
        db.query(ScanJob).filter_by(project_id=project_id)
        .order_by(ScanJob.created_at.desc()).all()
    )
    remediation_actions = db.query(RemediationAction).filter_by(project_id=project_id).all()
    scope_items = db.query(ScopeItem).filter_by(project_id=project_id).all()
    requirements = db.query(Requirement).filter_by(project_id=project_id).all()

    # Severity counts
    sev_counts = {s.value: 0 for s in FindingSeverity}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    # Status counts for findings
    status_counts: dict = {}
    for f in findings:
        status_counts[f.status] = status_counts.get(f.status, 0) + 1

    # Findings grouped by phase_tag / category
    by_phase: dict = {}
    for f in findings:
        key = f.phase_tag or "untagged"
        by_phase.setdefault(key, []).append(f)

    # Evidence by classification
    ev_by_class: dict = {}
    for ei in ev_items:
        key = ei.classification or "unclassified"
        ev_by_class[key] = ev_by_class.get(key, 0) + 1

    # Remediation index by finding_id
    rem_by_finding: dict = {}
    for ra in remediation_actions:
        rem_by_finding.setdefault(ra.finding_id, []).append(ra)

    # Task completion
    task_total = len(tasks)
    task_done = sum(1 for t in tasks if t.status in ("complete", "completed"))

    # Gate statuses from pack
    gate_statuses: list[dict] = []
    pack_data = None
    if project.pack_id:
        try:
            from app.services.methodology.loader import load_pack
            loaded = load_pack(project.pack_id)
            pack_data = loaded.model_dump()
            _gate_key_map = {
                "G1": "G1_scope", "G2": "G2_evidence_requests",
                "G3": "G3_evidence_complete", "G4": "G4_findings",
                "G5": "G5_qa", "G6": "G6_report", "G7": "G7_closure",
            }
            proj_gates = project.gates or {}
            for gate in loaded.review_gates:
                legacy_key = _gate_key_map.get(gate.id, gate.id)
                passed = bool(proj_gates.get(legacy_key) or proj_gates.get(gate.id))
                gate_statuses.append({
                    "id": gate.id, "label": gate.label,
                    "role": gate.required_role or "", "passed": passed,
                })
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "projects/report.html",
        {
            **base_ctx(user, db),
            "project": project,
            "client": client,
            "findings": findings,
            "sev_counts": sev_counts,
            "status_counts": status_counts,
            "by_phase": by_phase,
            "tasks": tasks,
            "task_total": task_total,
            "task_done": task_done,
            "ev_items": ev_items,
            "ev_requests": ev_requests,
            "ev_by_class": ev_by_class,
            "scan_jobs": scan_jobs,
            "remediation_actions": remediation_actions,
            "rem_by_finding": rem_by_finding,
            "scope_items": scope_items,
            "requirements": requirements,
            "gate_statuses": gate_statuses,
            "pack_data": pack_data,
        },
    )


@router.get("/projects/{project_id}/deliverables", response_class=HTMLResponse)
def deliverables_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    deliverables = (
        db.query(Deliverable)
        .filter_by(project_id=project_id)
        .order_by(Deliverable.kind, Deliverable.version.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "projects/deliverables.html",
        {**base_ctx(user, db), "project": project, "deliverables": deliverables},
    )


@router.post("/projects/{project_id}/deliverables/gap-matrix")
def generate_gap_matrix_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.gap_matrix import generate_gap_matrix
    out_dir = _BASE_DATA / project_id / "gap_matrix"
    xlsx_del, _ = generate_gap_matrix(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.gap_matrix",
        target_type="deliverable", target_id=xlsx_del.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/roadmap")
def generate_roadmap_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.roadmap import generate_roadmap
    out_dir = _BASE_DATA / project_id / "roadmap"
    md_del, _ = generate_roadmap(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.roadmap",
        target_type="deliverable", target_id=md_del.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/report")
def generate_report_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.report import generate_report
    out_dir = _BASE_DATA / project_id / "report"
    deliverable = generate_report(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.report",
        target_type="deliverable", target_id=deliverable.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/management-summary")
def generate_management_summary_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.management_summary import generate_management_summary
    out_dir = _BASE_DATA / project_id / "management_summary"
    deliverable = generate_management_summary(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.management_summary",
        target_type="deliverable", target_id=deliverable.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/client-action-plan")
def generate_client_action_plan_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.client_action_plan import generate_client_action_plan
    out_dir = _BASE_DATA / project_id / "client_action_plan"
    deliverable = generate_client_action_plan(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.client_action_plan",
        target_type="deliverable", target_id=deliverable.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/evidence-matrix")
def generate_evidence_matrix_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.evidence_matrix import generate_evidence_matrix
    out_dir = _BASE_DATA / project_id / "evidence_matrix"
    deliverable = generate_evidence_matrix(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.evidence_matrix",
        target_type="deliverable", target_id=deliverable.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/{del_id}/release")
def release_deliverable_web(
    project_id: str,
    del_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from app.services.audit import record_event
    deliverable = db.get(Deliverable, del_id)
    if deliverable and deliverable.project_id == project_id:
        deliverable.is_released = not deliverable.is_released
        record_event(
            db, action="deliverable.released" if deliverable.is_released else "deliverable.unrelease",
            target_type="deliverable", target_id=del_id,
            actor_id=user.id, project_id=project_id,
            after={"is_released": deliverable.is_released},
        )
        db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.post("/projects/{project_id}/deliverables/retest-report")
def generate_retest_report_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.audit import record_event
    from app.services.deliverables.retest_report import generate_retest_report
    out_dir = _BASE_DATA / project_id / "retest_report"
    deliverable = generate_retest_report(db, project, out_dir, user.id)
    db.flush()
    record_event(
        db, action="deliverable.generated.retest_report",
        target_type="deliverable", target_id=deliverable.id,
        actor_id=user.id, project_id=project_id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/deliverables", status_code=302)


@router.get("/projects/{project_id}/remediation", response_class=HTMLResponse)
def remediation_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.models.tasks import Finding
    actions = db.query(RemediationAction).filter_by(project_id=project_id).all()
    findings = db.query(Finding).filter_by(project_id=project_id).order_by(
        Finding.created_at.desc()
    ).all()
    return templates.TemplateResponse(
        request, "projects/remediation.html",
        {**base_ctx(user, db), "project": project, "actions": actions, "findings": findings},
    )
