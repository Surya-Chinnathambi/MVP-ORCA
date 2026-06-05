"""Web views — Approval queue."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.audit import decide_approval
from app.services.applier import apply_approval
from app.web.deps import LOGIN_REDIRECT, get_web_user

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
    pending = (
        db.query(ApprovalRequest)
        .filter_by(status=ApprovalStatus.pending)
        .order_by(ApprovalRequest.created_at.asc())
        .all()
    )
    return templates.TemplateResponse(
        request, "approvals/index.html",
        {"user": user, "approvals": pending},
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
    if approval and approval.status == ApprovalStatus.pending:
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
    if approval and approval.status == ApprovalStatus.pending:
        decide_approval(
            db,
            approval_id=approval_id,
            approved=False,
            decider_id=user.id,
            reason=reason or "Rejected via web UI",
        )
        db.commit()
    return RedirectResponse("/ui/approvals", status_code=302)
