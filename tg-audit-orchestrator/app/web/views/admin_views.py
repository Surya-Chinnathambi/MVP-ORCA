"""Web views — Admin pages (users, permissions, team management)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-admin"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/admin/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    users = db.query(User).order_by(User.created_at.asc()).all()
    roles = db.query(Role).order_by(Role.name).all()
    perms = db.query(Permission).all()
    perms_by_user: dict = {}
    for p in perms:
        perms_by_user.setdefault(p.user_id, []).append(p)
    return templates.TemplateResponse(
        request, "admin/users.html",
        {
            "user": user,
            "users": users,
            "roles": roles,
            "perms_by_user": perms_by_user,
            "role_names": [r.value for r in RoleName],
            "scope_levels": [s.value for s in ScopeLevel],
        },
    )


@router.post("/admin/users")
def create_user_web(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    from app.services.auth import hash_password
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        return RedirectResponse("/ui/admin/users?error=email_taken", status_code=302)
    new_user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse("/ui/admin/users", status_code=302)


@router.post("/admin/users/{target_user_id}/roles")
def assign_role_web(
    target_user_id: str,
    request: Request,
    role_name: str = Form(...),
    scope_level: str = Form(...),
    scope_id: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    role = db.query(Role).filter_by(name=role_name).first()
    if not role:
        return RedirectResponse("/ui/admin/users", status_code=302)
    perm = Permission(
        user_id=target_user_id,
        role_id=role.id,
        scope_level=scope_level,
        scope_id=scope_id.strip() or None,
    )
    db.add(perm)
    db.commit()
    return RedirectResponse("/ui/admin/users", status_code=302)


@router.post("/admin/users/{target_user_id}/roles/{perm_id}/remove")
def remove_role_web(
    target_user_id: str,
    perm_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    perm = db.get(Permission, perm_id)
    if perm and perm.user_id == target_user_id:
        db.delete(perm)
        db.commit()
    return RedirectResponse("/ui/admin/users", status_code=302)


@router.post("/admin/users/{target_user_id}/toggle-active")
def toggle_active_web(
    target_user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    target = db.get(User, target_user_id)
    if target and target.id != user.id:
        target.is_active = not target.is_active
        db.commit()
    return RedirectResponse("/ui/admin/users", status_code=302)
