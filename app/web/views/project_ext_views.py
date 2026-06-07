"""Extended project views — Timeline, Framework selector, Rules of Engagement."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.scope import FrameworkKey
from app.services.audit import record_event
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_web_user

router = APIRouter(tags=["web-projects-ext"])
templates = Jinja2Templates(directory="app/web/templates")

_FRAMEWORK_META = {
    "dpdp_act":        ("DPDP Act 2023",        "India's Digital Personal Data Protection Act — consent, data principal rights, breach notification"),
    "owasp_asvs":      ("OWASP ASVS 4.0",       "Application Security Verification Standard — architectural, auth, session, access control requirements"),
    "owasp_wstg":      ("OWASP WSTG",            "Web Security Testing Guide — methodology for web application penetration tests"),
    "owasp_api10":     ("OWASP API Top 10",      "The ten most critical API security risks and test cases"),
    "ptes":            ("PTES",                  "Penetration Testing Execution Standard — pre-engagement, intelligence gathering, exploitation, reporting"),
    "iso_27001":       ("ISO/IEC 27001:2022",    "Information security management system (ISMS) requirements and controls"),
    "iso_27002":       ("ISO/IEC 27002:2022",    "Information security controls reference — 93 controls across 4 themes"),
    "iso_27701":       ("ISO/IEC 27701:2019",    "Privacy information management extension to ISO 27001/27002"),
    "eu_gdpr":         ("EU GDPR",               "General Data Protection Regulation — lawful basis, data subject rights, controller obligations"),
    "nist":            ("NIST CSF 2.0",          "NIST Cybersecurity Framework — Govern, Identify, Protect, Detect, Respond, Recover"),
    "isaca":           ("ISACA COBIT",           "Control Objectives for IT — governance and management objectives for enterprise IT"),
    "tg_baseline":     ("TG Baseline",           "TechGuard Labs internal security baseline — minimum-security requirements for all engagements"),
}


# ── Timeline ──────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/timeline", response_class=HTMLResponse)
def timeline_page(
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
    milestones = project.timeline if isinstance(project.timeline, list) else []
    return templates.TemplateResponse(
        request, "projects/timeline.html",
        {
            **base_ctx(user, db),
            "project": project,
            "milestones": sorted(milestones, key=lambda m: m.get("date", "")),
        },
    )


@router.post("/projects/{project_id}/timeline")
def add_milestone(
    project_id: str,
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    status: str = Form("upcoming"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    milestones = list(project.timeline or [])
    milestones.append({"title": title.strip(), "date": date, "status": status, "notes": notes.strip()})
    project.timeline = milestones
    record_event(
        db, action="timeline.milestone_added",
        target_type="project", target_id=project_id,
        actor_id=user.id, project_id=project_id,
        after={"title": title, "date": date, "status": status},
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/timeline", status_code=302)


# ── Framework selector ────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/frameworks", response_class=HTMLResponse)
def frameworks_page(
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
    all_frameworks = [
        {"key": k.value, "title": _FRAMEWORK_META[k.value][0], "description": _FRAMEWORK_META[k.value][1]}
        for k in FrameworkKey
    ]
    return templates.TemplateResponse(
        request, "projects/frameworks.html",
        {**base_ctx(user, db), "project": project, "all_frameworks": all_frameworks},
    )


@router.post("/projects/{project_id}/frameworks")
def save_frameworks(
    project_id: str,
    request: Request,
    framework_ids: Optional[List[str]] = Form(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    valid_keys = {k.value for k in FrameworkKey}
    selected = [k for k in (framework_ids or []) if k in valid_keys]
    project.framework_ids = selected
    record_event(
        db, action="frameworks.updated",
        target_type="project", target_id=project_id,
        actor_id=user.id, project_id=project_id,
        after={"framework_ids": selected},
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/frameworks", status_code=302)


# ── Rules of Engagement ───────────────────────────────────────────────────────

@router.post("/projects/{project_id}/scope/roe")
async def save_roe(
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
    section = form.get("section", "")
    roe: dict = dict(project.roe_data or {})

    if section == "authorization":
        roe["authorization_text"] = (form.get("authorization_text") or "").strip()

    elif section == "testing_window":
        windows = list(roe.get("testing_windows") or [])
        start = form.get("window_start", "")
        end = form.get("window_end", "")
        desc = (form.get("window_description") or "").strip()
        if start and end:
            windows.append({"start": start, "end": end, "description": desc})
        roe["testing_windows"] = windows

    elif section == "escalation_contact":
        contacts = list(roe.get("escalation_contacts") or [])
        name = (form.get("contact_name") or "").strip()
        if name:
            contacts.append({
                "name": name,
                "role": (form.get("contact_role") or "").strip(),
                "phone": (form.get("contact_phone") or "").strip(),
                "email": (form.get("contact_email") or "").strip(),
            })
        roe["escalation_contacts"] = contacts

    elif section == "data_sensitivity":
        roe["data_sensitivity"] = {
            "classification": form.get("data_classification", "confidential"),
            "personal_data": form.get("personal_data") == "yes",
            "handling_notes": (form.get("handling_notes") or "").strip(),
        }

    project.roe_data = roe
    record_event(
        db, action="roe.updated",
        target_type="project", target_id=project_id,
        actor_id=user.id, project_id=project_id,
        after={"section": section},
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/scope", status_code=302)
