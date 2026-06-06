"""Web views — PT-Orc command reference and manual result import."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.scan import ScanJob, ScanJobStatus
from app.services.scan_runner import (
    PHASE_SCRIPTS, ROLE_DEFAULT_PHASES,
    build_command, build_report_pack_command, register_import,
)
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_highest_role, get_web_user

router = APIRouter(tags=["web-scans"])
templates = Jinja2Templates(directory="app/web/templates")

# Where PT-Orc scripts live on this machine
_SCRIPTS_DIR = "/home/kali/MVP_ORCA/pt-orc/scripts"
_TIERS = ["baseline", "standard", "deep"]


@router.get("/projects/{project_id}/scans", response_class=HTMLResponse)
def scans_page(
    project_id: str,
    request: Request,
    host: str = "",
    tier: str = "standard",
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)

    user_role = get_highest_role(user, db) or "default"
    # Normalise RoleName enum → string
    if hasattr(user_role, "value"):
        user_role = user_role.value

    default_phases = ROLE_DEFAULT_PHASES.get(user_role, ROLE_DEFAULT_PHASES["default"])

    # Build per-phase command blocks (only when host is supplied)
    phase_commands: list[dict] = []
    if host.strip():
        for phase_key, (script, label, role) in PHASE_SCRIPTS.items():
            cmd = build_command(_SCRIPTS_DIR, phase_key, host.strip(), tier)
            phase_commands.append({
                "key": phase_key,
                "label": label,
                "script": script,
                "role": role,
                "cmd": cmd,
                "selected": phase_key in default_phases,
            })

    report_cmd = ""
    if host.strip():
        report_cmd = build_report_pack_command(_SCRIPTS_DIR, project_id)

    import_jobs = (
        db.query(ScanJob)
        .filter_by(project_id=project_id)
        .order_by(ScanJob.created_at.desc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request, "projects/scans.html",
        {
            **base_ctx(user, db),
            "project": project,
            "host": host.strip(),
            "tier": tier,
            "tiers": _TIERS,
            "all_phases": PHASE_SCRIPTS,
            "default_phases": default_phases,
            "phase_commands": phase_commands,
            "report_cmd": report_cmd,
            "import_jobs": import_jobs,
            "user_role": user_role,
            "ScanJobStatus": ScanJobStatus,
            "scripts_dir": _SCRIPTS_DIR,
        },
    )


@router.post("/projects/{project_id}/scans/import")
async def import_results(
    project_id: str,
    request: Request,
    run_dir: str = Form(...),
    host: str = Form(""),
    tier: str = Form("standard"),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    """Register a completed PT-Orc run directory and import its findings."""
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)

    form = await request.form()
    phases = list(form.getlist("phases")) or list(PHASE_SCRIPTS.keys())

    job = register_import(
        db,
        project_id=project_id,
        run_dir=run_dir.strip(),
        host=host.strip() or "unknown",
        phases=phases,
        tier=tier,
        user_id=user.id,
    )
    return RedirectResponse(
        f"/ui/projects/{project_id}/scans/{job.id}", status_code=302
    )


@router.get("/projects/{project_id}/scans/{job_id}", response_class=HTMLResponse)
def import_detail(
    project_id: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    job = db.get(ScanJob, job_id)
    if not project or not job or job.project_id != project_id:
        return RedirectResponse(f"/ui/projects/{project_id}/scans", status_code=302)

    return templates.TemplateResponse(
        request, "projects/scan_detail.html",
        {
            **base_ctx(user, db),
            "project": project,
            "job": job,
            "PHASE_SCRIPTS": PHASE_SCRIPTS,
            "ScanJobStatus": ScanJobStatus,
        },
    )
