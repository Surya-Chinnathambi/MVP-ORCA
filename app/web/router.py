"""Web UI router — assembles all view sub-routers under /ui prefix."""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.web.views import (
    admin_views,
    approval_views,
    auth_views,
    client_views,
    deliverable_views,
    evidence_views,
    portal_views,
    project_views,
    task_views,
)

router = APIRouter(prefix="/ui")

# Separate top-level router (no /ui prefix) for client portal
portal_router = portal_views.router

router.include_router(auth_views.router)
router.include_router(client_views.router)
router.include_router(project_views.router)
router.include_router(evidence_views.router)
router.include_router(task_views.router)
router.include_router(deliverable_views.router)
router.include_router(approval_views.router)
router.include_router(admin_views.router)


@router.get("/")
def ui_root():
    return RedirectResponse("/ui/clients", status_code=302)
