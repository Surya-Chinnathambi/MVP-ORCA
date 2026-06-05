"""Web auth views — login form and logout."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import User
from app.services.auth import verify_password

router = APIRouter(tags=["web-auth"])
templates = Jinja2Templates(directory="app/web/templates")


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
        return RedirectResponse("/ui/clients", status_code=302)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Invalid email or password"}, status_code=401
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/ui/login", status_code=302)
