"""Web views — Project dashboard, scope, and pack pages."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Client, Project
from app.models.evidence import EvidenceItem, EvidenceRequest
from app.models.scope import Requirement, ScopeItem
from app.models.tasks import Finding, Task
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-projects"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_dashboard(
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
    return templates.TemplateResponse(
        request, "projects/dashboard.html",
        {
            "user": user,
            "project": project,
            "client": client,
            "findings_count": db.query(Finding).filter_by(project_id=project_id).count(),
            "tasks_count": db.query(Task).filter_by(project_id=project_id).count(),
            "evidence_count": db.query(EvidenceItem).filter_by(project_id=project_id).count(),
            "open_requests": db.query(EvidenceRequest).filter_by(
                project_id=project_id, status="open"
            ).count(),
        },
    )


@router.get("/projects/{project_id}/scope", response_class=HTMLResponse)
def scope_page(
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
    scope_items = db.query(ScopeItem).filter_by(project_id=project_id).all()
    return templates.TemplateResponse(
        request, "projects/scope.html",
        {"user": user, "project": project, "scope_items": scope_items},
    )


@router.post("/projects/{project_id}/scope")
def add_scope_item(
    project_id: str,
    request: Request,
    kind: str = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from app.services.audit import request_approval
    item = ScopeItem(project_id=project_id, kind=kind, value=value, approved=False)
    db.add(item)
    db.flush()
    request_approval(
        db,
        project_id=project_id,
        target_type="scope_item",
        target_id=item.id,
        reason=f"New scope item: {kind} — {value}",
        approver_role="partner",
        requested_by=user.id,
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/scope", status_code=302)


@router.get("/projects/{project_id}/pack", response_class=HTMLResponse)
def pack_page(
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
    pack_data = None
    if project.pack_id:
        from app.services.methodology.loader import load_pack
        try:
            pack_data = load_pack(project.pack_id).model_dump()
        except Exception:
            pass
    reqs = db.query(Requirement).filter_by(project_id=project_id).count()
    return templates.TemplateResponse(
        request, "projects/pack.html",
        {"user": user, "project": project, "pack_data": pack_data, "requirements_count": reqs},
    )


@router.post("/projects/{project_id}/pack/generate")
def generate_plan_web(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project or not project.pack_id:
        return RedirectResponse(f"/ui/projects/{project_id}/pack", status_code=302)
    from app.services.methodology.loader import load_pack
    from app.services.methodology.plan import generate_plan
    pack = load_pack(project.pack_id)
    generate_plan(db, project, pack)
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}", status_code=302)
