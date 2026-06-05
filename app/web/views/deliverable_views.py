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
    actions = db.query(RemediationAction).filter_by(project_id=project_id).all()
    return templates.TemplateResponse(
        request, "projects/remediation.html",
        {"user": user, "project": project, "actions": actions},
    )
