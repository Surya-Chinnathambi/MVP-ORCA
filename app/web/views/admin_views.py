"""Web views — Admin pages (users & permissions)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import Role, User
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
    return templates.TemplateResponse(
        request, "admin/users.html",
        {"user": user, "users": users, "roles": roles},
    )
