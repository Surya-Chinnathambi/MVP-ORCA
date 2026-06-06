"""Web views — Approval queue with role-based gate enforcement."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.audit import decide_approval
from app.services.applier import apply_approval
from app.web.deps import LOGIN_REDIRECT, base_ctx, can_approve, get_user_roles, get_web_user

router = APIRouter(tags=["web-approvals"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/approvals", response_class=HTMLResponse)
def approvals_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT

    user_roles = get_user_roles(user, db)

    # Show only approvals the current user is authorised to act on
    pending = (
        db.query(ApprovalRequest)
        .filter_by(status=ApprovalStatus.pending)
        .order_by(ApprovalRequest.created_at.asc())
        .all()
    )

    # Annotate each approval with whether this user can act on it
    annotated = []
    for a in pending:
        can_act = can_approve(user, a.approver_role, db, project_id=a.project_id)
        annotated.append({"approval": a, "can_act": can_act})

    return templates.TemplateResponse(
        request, "approvals/index.html",
        {
            **base_ctx(user, db),
            "approvals": annotated,
            "user_roles": user_roles,
        },
    )


@router.post("/approvals/{approval_id}/approve")
def approve_web(
    approval_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    approval = db.get(ApprovalRequest, approval_id)
    if not approval or approval.status != ApprovalStatus.pending:
        return RedirectResponse("/ui/approvals", status_code=302)

    # Role guard: user must hold the required approver_role
    if not can_approve(user, approval.approver_role, db, project_id=approval.project_id):
        return RedirectResponse(
            f"/ui/approvals?error=insufficient_role&required={approval.approver_role}",
            status_code=302,
        )

    decide_approval(db, approval_id=approval_id, approved=True, decider_id=user.id)
    try:
        apply_approval(db, approval)
    except Exception:
        pass
    db.commit()
    return RedirectResponse("/ui/approvals", status_code=302)


@router.post("/approvals/{approval_id}/reject")
def reject_web(
    approval_id: str,
    request: Request,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    approval = db.get(ApprovalRequest, approval_id)
    if not approval or approval.status != ApprovalStatus.pending:
        return RedirectResponse("/ui/approvals", status_code=302)

    # Role guard
    if not can_approve(user, approval.approver_role, db, project_id=approval.project_id):
        return RedirectResponse(
            f"/ui/approvals?error=insufficient_role&required={approval.approver_role}",
            status_code=302,
        )

    decide_approval(
        db,
        approval_id=approval_id,
        approved=False,
        decider_id=user.id,
        reason=reason or "Rejected via web UI",
    )
    db.commit()
    return RedirectResponse("/ui/approvals", status_code=302)
