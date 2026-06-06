"""Client portal views — strictly scoped to client_approver / client_contributor / readonly."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.delivery import Deliverable
from app.models.evidence import EvidenceRequest, EvidenceRequestStatus
from app.models.tasks import Finding, FindingStatus, Task
from app.models.users import Permission, Role, RoleName, User
from app.services.audit import record_event, request_approval

router = APIRouter(prefix="/portal", tags=["portal"])
templates = Jinja2Templates(directory="app/web/templates")

_PORTAL_ROLES = frozenset({
    RoleName.client_approver.value,
    RoleName.client_contributor.value,
    RoleName.readonly.value,
})


# ── Portal guard ──────────────────────────────────────────────────────────────

def _portal_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Reject any user who does not hold at least one portal role."""
    role_ids = [r.id for r in db.query(Role).filter(Role.name.in_(_PORTAL_ROLES)).all()]
    perm = db.query(Permission).filter(
        Permission.user_id == current_user.id,
        Permission.role_id.in_(role_ids),
    ).first()
    if perm is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client portal access required")
    return current_user


def _scoped_project_id(user: User, db: Session, requested: Optional[str] = None) -> str:
    """Return the project_id the portal user is authorised to view.

    Raises 403 if the user has no project-scoped portal permission,
    or if a specific project_id was requested but not allowed.
    """
    role_ids = [r.id for r in db.query(Role).filter(Role.name.in_(_PORTAL_ROLES)).all()]
    perms = db.query(Permission).filter(
        Permission.user_id == user.id,
        Permission.role_id.in_(role_ids),
        Permission.scope_id.isnot(None),
    ).all()
    allowed = {p.scope_id for p in perms}
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No project access")
    if requested:
        if requested not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to project")
        return requested
    return next(iter(allowed))


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def portal_dashboard(
    request: Request,
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    from app.models.clients import Project
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    findings = (
        db.query(Finding)
        .filter_by(project_id=project_id, status=FindingStatus.client_shared.value)
        .all()
    )
    released_deliverables = (
        db.query(Deliverable)
        .filter_by(project_id=project_id, is_released=True)
        .all()
    )
    return templates.TemplateResponse(request, "portal/dashboard.html", {
        "user": user,
        "project": project,
        "findings": findings,
        "released_deliverables": released_deliverables,
    })


# ── Upload ────────────────────────────────────────────────────────────────────

@router.get("/upload", response_class=HTMLResponse)
def portal_upload_form(
    request: Request,
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    evidence_requests = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open.value)
        .all()
    )
    return templates.TemplateResponse(request, "portal/upload.html", {
        "user": user,
        "evidence_requests": evidence_requests,
        "message": None,
        "success": False,
    })


@router.post("/upload", response_class=HTMLResponse)
async def portal_upload_submit(
    request: Request,
    file: UploadFile = File(...),
    evidence_request_id: Optional[str] = Form(default=None),
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    from app.services.evidence.ingest import ingest_file

    project_id = _scoped_project_id(user, db)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if evidence_request_id:
        er = db.get(EvidenceRequest, evidence_request_id)
        if er is None or er.project_id != project_id:
            raise HTTPException(status_code=404, detail="Evidence request not found")

    item = ingest_file(
        db,
        project_id=project_id,
        data=data,
        filename=file.filename or "upload",
        evidence_request_id=evidence_request_id or None,
        uploaded_by_id=user.id,
    )
    record_event(
        db,
        action="client_upload",
        target_type="evidence_item",
        target_id=item.id,
        actor_id=user.id,
        project_id=project_id,
        after={"filename": file.filename, "lifecycle_state": item.internal_lifecycle_state},
    )
    db.commit()

    evidence_requests = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id, status=EvidenceRequestStatus.open.value)
        .all()
    )
    return templates.TemplateResponse(request, "portal/upload.html", {
        "user": user,
        "evidence_requests": evidence_requests,
        "message": f"File '{file.filename}' uploaded successfully.",
        "success": True,
    })


# ── Questions ─────────────────────────────────────────────────────────────────

@router.get("/questions", response_class=HTMLResponse)
def portal_questions(
    request: Request,
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    evidence_requests = (
        db.query(EvidenceRequest)
        .filter_by(project_id=project_id)
        .all()
    )
    return templates.TemplateResponse(request, "portal/questions.html", {
        "user": user,
        "evidence_requests": evidence_requests,
    })


@router.post("/questions/{er_id}/answer", response_class=HTMLResponse)
def portal_answer_question(
    er_id: str,
    request: Request,
    answer: str = Form(...),
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    er = db.get(EvidenceRequest, er_id)
    if er is None or er.project_id != project_id:
        raise HTTPException(status_code=404, detail="Evidence request not found")

    prefix = f"[Client answer from {user.email}]: "
    er.description = (er.description or "") + "\n\n" + prefix + answer
    record_event(
        db,
        action="client_answer",
        target_type="evidence_request",
        target_id=er_id,
        actor_id=user.id,
        project_id=project_id,
        after={"answer_preview": answer[:100]},
    )
    db.commit()
    return HTMLResponse(content="<span class='text-green-700 text-xs font-medium'>Answer submitted.</span>")


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.get("/tasks", response_class=HTMLResponse)
def portal_tasks(
    request: Request,
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    tasks = db.query(Task).filter_by(project_id=project_id).all()
    return templates.TemplateResponse(request, "portal/tasks.html", {
        "user": user,
        "tasks": tasks,
    })


@router.post("/tasks/{task_id}/comment", response_class=HTMLResponse)
def portal_task_comment(
    task_id: str,
    comment: str = Form(...),
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    project_id = _scoped_project_id(user, db)
    task = db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    record_event(
        db,
        action="client_comment",
        target_type="task",
        target_id=task_id,
        actor_id=user.id,
        project_id=project_id,
        reason=comment,
    )
    db.commit()
    return HTMLResponse(content="Comment recorded.")


# ── Risk acceptance ───────────────────────────────────────────────────────────

@router.post("/accept-risk/{finding_id}")
def portal_accept_risk(
    finding_id: str,
    user: User = Depends(_portal_user),
    db: Session = Depends(get_db),
):
    """Create an ApprovalRequest for risk acceptance — never change status directly."""
    project_id = _scoped_project_id(user, db)
    finding = db.get(Finding, finding_id)
    if finding is None or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    request_approval(
        db,
        project_id=project_id,
        target_type="finding",
        target_id=finding_id,
        reason=f"Client risk acceptance requested by {user.email}",
        approver_role=RoleName.partner.value,
        change_before={"status": finding.status},
        change_after={"status": FindingStatus.risk_accepted.value},
        requested_by=user.id,
    )
    record_event(
        db,
        action="client_accept_risk_request",
        target_type="finding",
        target_id=finding_id,
        actor_id=user.id,
        project_id=project_id,
        reason="Client submitted risk acceptance via portal",
    )
    db.commit()
    return RedirectResponse("/portal/dashboard", status_code=303)
