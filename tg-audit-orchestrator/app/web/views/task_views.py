"""Web views — Tasks board."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.tasks import Finding, Task, TaskKind, TaskStatus
from app.models.users import User
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_web_user

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
    all_users = db.query(User).filter_by(is_active=True).all()
    return templates.TemplateResponse(
        request, "projects/tasks.html",
        {
            **base_ctx(user, db),
            "project": project,
            "tasks": tasks,
            "task_kinds": [k.value for k in TaskKind],
            "task_statuses": [s.value for s in TaskStatus],
            "all_users": all_users,
        },
    )


@router.post("/projects/{project_id}/tasks")
def create_task_web(
    project_id: str,
    request: Request,
    kind: str = Form(...),
    title: str = Form(...),
    assignee_id: str = Form(""),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from datetime import date
    td = None
    if due_date:
        try:
            td = date.fromisoformat(due_date)
        except ValueError:
            pass
    task = Task(
        project_id=project_id,
        kind=kind,
        title=title,
        status=TaskStatus.planned.value,
        assignee_id=assignee_id.strip() or None,
        due_date=td,
    )
    db.add(task)
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/tasks", status_code=302)


@router.post("/projects/{project_id}/tasks/{task_id}/status")
def update_task_status_web(
    project_id: str,
    task_id: str,
    request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    task = db.get(Task, task_id)
    if task and task.project_id == project_id:
        task.status = new_status
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/tasks", status_code=302)
