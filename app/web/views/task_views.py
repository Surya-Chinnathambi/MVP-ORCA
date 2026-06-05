"""Web views — Tasks and Findings."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.tasks import Finding, Task
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-tasks"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/projects/{project_id}/tasks", response_class=HTMLResponse)
def tasks_page(
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
    tasks = (
        db.query(Task)
        .filter_by(project_id=project_id)
        .order_by(Task.due_date.asc().nullslast(), Task.created_at.asc())
        .all()
    )
    return templates.TemplateResponse(
        request, "projects/tasks.html",
        {"user": user, "project": project, "tasks": tasks},
    )


@router.get("/projects/{project_id}/findings", response_class=HTMLResponse)
def findings_page(
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

    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings = db.query(Finding).filter_by(project_id=project_id).all()
    findings.sort(key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    return templates.TemplateResponse(
        request, "projects/findings.html",
        {"user": user, "project": project, "findings": findings},
    )
