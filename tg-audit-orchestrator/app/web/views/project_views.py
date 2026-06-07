"""Web views — Project dashboard, scope, and pack pages."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Client, Project
from app.models.delivery import RemediationAction
from app.models.evidence import EvidenceItem, EvidenceRequest
from app.models.scope import Requirement, ScopeItem
from app.models.tasks import Finding, FindingSeverity, FindingStatus, Task
from app.models.users import Permission, ScopeLevel
from app.models.workflow import AuditTrailEvent
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_web_user

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
    team_count = (
        db.query(Permission)
        .filter_by(scope_level=ScopeLevel.project, scope_id=project_id)
        .count()
    )
    return templates.TemplateResponse(
        request, "projects/dashboard.html",
        {
            **base_ctx(user, db),
            "project": project,
            "client": client,
            "findings_count": db.query(Finding).filter_by(project_id=project_id).count(),
            "tasks_count": db.query(Task).filter_by(project_id=project_id).count(),
            "evidence_count": db.query(EvidenceItem).filter_by(project_id=project_id).count(),
            "open_requests": db.query(EvidenceRequest).filter_by(
                project_id=project_id, status="open"
            ).count(),
            "team_count": team_count,
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
        {**base_ctx(user, db), "project": project, "scope_items": scope_items},
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
        approver_role="pm",
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

    from app.services.methodology.loader import load_pack, available_packs
    pack_data = None
    gate_statuses: list[dict] = []
    if project.pack_id:
        try:
            loaded = load_pack(project.pack_id)
            pack_data = loaded.model_dump()
            # Build gate status: match gate.id prefix (G1, G2…) against project.gates dict
            proj_gates: dict = project.gates or {}
            _gate_key_map = {
                "G1": "G1_scope", "G2": "G2_evidence_requests",
                "G3": "G3_evidence_complete", "G4": "G4_findings",
                "G5": "G5_qa", "G6": "G6_report", "G7": "G7_closure",
            }
            for gate in loaded.review_gates:
                legacy_key = _gate_key_map.get(gate.id, gate.id)
                passed = bool(proj_gates.get(legacy_key) or proj_gates.get(gate.id))
                gate_statuses.append({
                    "id": gate.id,
                    "label": gate.label,
                    "role": gate.required_role or "",
                    "passed": passed,
                })
        except Exception:
            pass

    reqs = db.query(Requirement).filter_by(project_id=project_id).count()
    all_packs = [
        {"key": k, "title": k.replace("_", " ").title()}
        for k in available_packs()
    ]
    # Enrich titles with proper names
    _pack_titles = {
        "vapt": "VAPT Assessment Pack v2",
        "dpdp": "DPDP Readiness Pack",
        "gdpr_gap": "GDPR Gap Assessment Pack",
        "iso_27001_readiness": "ISO 27001:2022 Readiness Pack",
        "iso_27002_control_review": "ISO 27002:2022 Control Review Pack",
        "iso_27701_privacy": "ISO 27701:2019 Privacy Pack",
        "incident_response": "Incident Response Capability Pack",
        "cloud_posture": "Cloud Security Posture Pack",
        "ai_governance": "AI Governance and Risk Pack",
        "vendor_risk": "Third-Party & Vendor Risk Pack",
        "cyber_strategy": "Cyber Strategy and Roadmap Pack",
        "grc_maturity": "GRC Maturity Assessment Pack",
    }
    for p in all_packs:
        p["title"] = _pack_titles.get(p["key"], p["title"])

    return templates.TemplateResponse(
        request, "projects/pack.html",
        {
            **base_ctx(user, db),
            "project": project,
            "pack_data": pack_data,
            "requirements_count": reqs,
            "gate_statuses": gate_statuses,
            "all_packs": all_packs,
        },
    )


@router.post("/projects/{project_id}/pack/attach")
def attach_pack_web(
    project_id: str,
    request: Request,
    pack_key: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    project = db.get(Project, project_id)
    if not project:
        return RedirectResponse("/ui/clients", status_code=302)
    from app.services.methodology.loader import load_pack
    try:
        load_pack(pack_key)  # validate the key exists on disk
    except FileNotFoundError:
        return RedirectResponse(f"/ui/projects/{project_id}/pack", status_code=302)
    project.pack_id = pack_key
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/pack", status_code=302)


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
    findings = db.query(Finding).filter_by(project_id=project_id).order_by(
        Finding.created_at.desc()
    ).all()
    return templates.TemplateResponse(
        request, "projects/findings.html",
        {
            **base_ctx(user, db),
            "project": project,
            "findings": findings,
            "severities": [s.value for s in FindingSeverity],
        },
    )


@router.post("/projects/{project_id}/findings")
def create_finding_web(
    project_id: str,
    request: Request,
    title: str = Form(...),
    severity: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from app.services.audit import record_event
    finding = Finding(
        project_id=project_id,
        title=title,
        severity=severity,
        status=FindingStatus.draft.value,
        owner_id=user.id,
        description=description or None,
    )
    db.add(finding)
    db.flush()
    record_event(
        db, action="finding.created",
        target_type="finding", target_id=finding.id,
        actor_id=user.id, project_id=project_id,
        after={"title": title, "severity": severity, "status": "draft"},
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/findings", status_code=302)


@router.post("/projects/{project_id}/findings/{finding_id}/status")
def update_finding_status_web(
    project_id: str,
    finding_id: str,
    request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from app.services.audit import record_event
    finding = db.get(Finding, finding_id)
    if finding and finding.project_id == project_id:
        old_status = finding.status
        finding.status = new_status
        record_event(
            db, action="finding.status_changed",
            target_type="finding", target_id=finding_id,
            actor_id=user.id, project_id=project_id,
            before={"status": old_status}, after={"status": new_status},
        )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/findings", status_code=302)


@router.get("/projects/{project_id}/audit", response_class=HTMLResponse)
def audit_trail_page(
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
    events = (
        db.query(AuditTrailEvent)
        .filter_by(project_id=project_id)
        .order_by(AuditTrailEvent.ts.desc())
        .limit(200)
        .all()
    )
    from app.models.users import User as UserModel
    actor_ids = {e.actor_id for e in events if e.actor_id}
    actors = {u.id: u for u in db.query(UserModel).filter(UserModel.id.in_(actor_ids)).all()} if actor_ids else {}
    return templates.TemplateResponse(
        request, "projects/audit.html",
        {**base_ctx(user, db), "project": project, "events": events, "actors": actors},
    )


@router.post("/projects/{project_id}/remediation")
def create_remediation_web(
    project_id: str,
    request: Request,
    finding_id: str = Form(...),
    action: str = Form(...),
    target_date: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from datetime import date
    from app.services.audit import record_event
    td = None
    if target_date:
        try:
            td = date.fromisoformat(target_date)
        except ValueError:
            pass
    ra = RemediationAction(
        project_id=project_id,
        finding_id=finding_id,
        action=action,
        owner_id=user.id,
        status="open",
        target_date=td,
    )
    db.add(ra)
    db.flush()
    record_event(
        db, action="remediation.created",
        target_type="remediation_action", target_id=ra.id,
        actor_id=user.id, project_id=project_id,
        after={"finding_id": finding_id, "action": action[:80]},
    )
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/remediation", status_code=302)


@router.post("/projects/{project_id}/remediation/{action_id}/status")
def update_remediation_status_web(
    project_id: str,
    action_id: str,
    request: Request,
    new_status: str = Form(...),
    residual_risk: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    ra = db.get(RemediationAction, action_id)
    if ra and ra.project_id == project_id:
        ra.status = new_status
        if residual_risk:
            ra.residual_risk = residual_risk
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/remediation", status_code=302)
