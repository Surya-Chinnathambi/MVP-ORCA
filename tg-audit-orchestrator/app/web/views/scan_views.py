"""Web views — Scan runner (trigger PT-Orc phases from the UI)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.scan import ScanJob, ScanJobStatus
from app.services.scan_runner import PHASE_SCRIPTS, tail_log, trigger_scan
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-scans"])
templates = Jinja2Templates(directory="app/web/templates")

_ALL_PHASES = [
    ("01", "DNS Recon",           "Passive / active DNS enumeration"),
    ("02", "IP Analysis",         "Whois, ASN, geo-IP lookup"),
    ("03", "Comprehensive Scan",  "Full port scan (needs sudo for raw sockets)"),
    ("04", "TLS Review",          "TLS version, cipher, certificate checks"),
    ("05", "Web Enumeration",     "Directory brute-force, tech detection"),
    ("06", "WordPress Scan",      "WPScan plugin / theme enumeration"),
    ("07", "Service Verification","Banner grab, CVE check on open ports"),
    ("08", "App / API Review",    "OWASP API Top-10, auth bypass, CORS, rate-limit"),
    ("09", "AI / LLM Review",     "LLM endpoint discovery, prompt injection"),
]

_TIERS = ["baseline", "standard", "deep"]


@router.get("/projects/{project_id}/scans", response_class=HTMLResponse)
def scans_page(
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
    jobs = (
        db.query(ScanJob)
        .filter_by(project_id=project_id)
        .order_by(ScanJob.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "projects/scans.html",
        {
            "user": user,
            "project": project,
            "jobs": jobs,
            "all_phases": _ALL_PHASES,
            "tiers": _TIERS,
            "ScanJobStatus": ScanJobStatus,
        },
    )


@router.post("/projects/{project_id}/scans")
async def create_scan(
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

    form = await request.form()
    host = form.get("host", "").strip()
    tier = form.get("tier", "standard")
    api_key = form.get("api_key", "").strip() or None
    phases: list[str] = form.getlist("phases")

    if not host:
        return RedirectResponse(f"/ui/projects/{project_id}/scans", status_code=302)
    if not phases:
        phases = ["08", "09"]

    job = trigger_scan(
        db,
        project_id=project_id,
        host=host,
        phases=phases,
        tier=tier,
        api_key=api_key,
        user_id=user.id,
    )
    return RedirectResponse(
        f"/ui/projects/{project_id}/scans/{job.id}", status_code=302
    )


@router.get("/projects/{project_id}/scans/{job_id}", response_class=HTMLResponse)
def scan_detail(
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
    log_text = tail_log(job, lines=120)
    return templates.TemplateResponse(
        request, "projects/scan_detail.html",
        {
            "user": user,
            "project": project,
            "job": job,
            "log_text": log_text,
            "ScanJobStatus": ScanJobStatus,
            "PHASE_SCRIPTS": PHASE_SCRIPTS,
        },
    )


@router.get(
    "/projects/{project_id}/scans/{job_id}/status",
    response_class=HTMLResponse,
)
def scan_status_fragment(
    project_id: str,
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    """HTMX polling endpoint — returns a status+log fragment."""
    if user is None:
        return HTMLResponse("", status_code=200)
    db.expire_all()  # ensure fresh read
    job = db.get(ScanJob, job_id)
    if not job:
        return HTMLResponse("<p class='text-red-500'>Job not found</p>")
    log_text = tail_log(job, lines=80)
    active = job.status in (ScanJobStatus.queued.value, ScanJobStatus.running.value)
    return templates.TemplateResponse(
        request, "projects/scan_status_fragment.html",
        {
            "job": job,
            "log_text": log_text,
            "active": active,
            "ScanJobStatus": ScanJobStatus,
        },
    )
