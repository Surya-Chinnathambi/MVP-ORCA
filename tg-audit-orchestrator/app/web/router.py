"""Web UI router — assembles all view sub-routers under /ui prefix."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.web.deps import base_ctx, get_web_user
from app.web.views import (
    admin_views,
    approval_views,
    auth_views,
    client_views,
    deliverable_views,
    evidence_views,
    portal_views,
    project_views,
    scan_views,
    task_views,
    team_views,
)

router = APIRouter(prefix="/ui")
_templates = Jinja2Templates(directory="app/web/templates")

# Separate top-level router (no /ui prefix) for client portal
portal_router = portal_views.router

router.include_router(auth_views.router)
router.include_router(client_views.router)
router.include_router(project_views.router)
router.include_router(evidence_views.router)
router.include_router(task_views.router)
router.include_router(deliverable_views.router)
router.include_router(approval_views.router)
router.include_router(scan_views.router)
router.include_router(team_views.router)
router.include_router(admin_views.router)


@router.get("/")
def ui_root():
    return RedirectResponse("/ui/clients", status_code=302)


@router.get("/forbidden", response_class=HTMLResponse)
def forbidden_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    return _templates.TemplateResponse(
        request, "forbidden.html",
        {**base_ctx(user, db)},
        status_code=403,
    )
