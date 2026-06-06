"""Web views — Deliverables builder and remediation tracker."""
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.delivery import Deliverable, RemediationAction
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-deliverables"])
templates = Jinja2Templates(directory="app/web/templates")

_BASE_DATA = Path("data/deliverables")


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
        {"user": user, "project": project, "deliverables": deliverables},
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
        {"user": user, "project": project, "actions": actions, "findings": findings},
    )
