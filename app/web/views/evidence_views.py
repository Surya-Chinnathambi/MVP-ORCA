"""Web views — Evidence requests and evidence items."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.evidence import EvidenceItem, EvidenceRequest
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-evidence"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/projects/{project_id}/evidence-requests", response_class=HTMLResponse)
def evidence_requests_page(
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
    ev_requests = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id)
        .order_by(EvidenceRequest.status)
        .all()
    )
    return templates.TemplateResponse(
        request, "projects/evidence_requests.html",
        {"user": user, "project": project, "evidence_requests": ev_requests},
    )


@router.get("/projects/{project_id}/evidence", response_class=HTMLResponse)
def evidence_page(
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
    items = (
        db.query(EvidenceItem)
        .filter_by(project_id=project_id)
        .order_by(EvidenceItem.ingested_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "projects/evidence.html",
        {"user": user, "project": project, "evidence_items": items},
    )
