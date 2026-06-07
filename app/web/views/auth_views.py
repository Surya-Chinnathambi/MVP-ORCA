"""Web auth views — login, logout, and terms acceptance."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import User
from app.services.auth import verify_password
from app.services.audit import record_event
from app.web.deps import base_ctx, get_web_user, LOGIN_REDIRECT

router = APIRouter(tags=["web-auth"])
templates = Jinja2Templates(directory="app/web/templates")

_PORTAL_ROLES = frozenset({"client_approver", "client_contributor", "readonly"})


def _is_portal_only_user(user: User, db: Session) -> bool:
    from app.models.users import Permission, Role
    roles = (
        db.query(Role.name)
        .join(Permission, Permission.role_id == Role.id)
        .filter(Permission.user_id == user.id)
        .all()
    )
    role_names = {r[0] for r in roles}
    return bool(role_names) and role_names.issubset(_PORTAL_ROLES)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/ui/clients", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(email=email).first()
    if user and user.is_active and verify_password(password, user.password_hash):
        request.session["user_id"] = user.id
        if not user.terms_accepted_at:
            return RedirectResponse("/ui/terms", status_code=302)
        if _is_portal_only_user(user, db):
            return RedirectResponse("/portal/dashboard", status_code=302)
        return RedirectResponse("/ui/clients", status_code=302)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Invalid email or password"}, status_code=401
    )


@router.get("/terms", response_class=HTMLResponse)
def terms_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    return templates.TemplateResponse(
        request, "terms.html",
        {**base_ctx(user, db), "already_accepted": bool(user.terms_accepted_at)},
    )


@router.post("/terms/accept")
def terms_accept(
    request: Request,
    agree: str = Form(default=""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    if agree != "1":
        return RedirectResponse("/ui/terms", status_code=302)

    now = datetime.now(timezone.utc)
    user.terms_accepted_at = now
    record_event(
        db,
        action="terms.accepted",
        target_type="user",
        target_id=user.id,
        actor_id=user.id,
        after={"terms_version": "TG-AO-TOS-2026-06", "accepted_at": now.isoformat()},
    )
    db.commit()

    if _is_portal_only_user(user, db):
        return RedirectResponse("/portal/dashboard", status_code=302)
    return RedirectResponse("/ui/clients", status_code=302)


@router.post("/workmode/set")
def set_workmode(
    request: Request,
    mode: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    _VALID = {"pm", "analyst", "reviewer", "deliverable"}
    if mode in _VALID:
        user.last_work_mode = mode
        db.commit()
    referer = request.headers.get("referer", "/ui/clients")
    return RedirectResponse(referer, status_code=302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/ui/login", status_code=302)
