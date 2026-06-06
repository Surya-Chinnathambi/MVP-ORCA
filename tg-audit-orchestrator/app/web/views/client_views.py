"""Web views — Clients dashboard."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Client, Project
from app.web.deps import LOGIN_REDIRECT, get_web_user

router = APIRouter(tags=["web-clients"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/clients", response_class=HTMLResponse)
def clients_page(request: Request, db: Session = Depends(get_db), user=Depends(get_web_user)):
    if user is None:
        return LOGIN_REDIRECT
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    return templates.TemplateResponse(request, "clients/index.html", {"user": user, "clients": clients})


@router.post("/clients")
def create_client_web(
    request: Request,
    name: str = Form(...),
    sector: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    c = Client(entity_name=name, sector=sector or None)
    db.add(c)
    db.commit()
    return RedirectResponse("/ui/clients", status_code=302)


@router.get("/clients/{client_id}/projects/new", response_class=HTMLResponse)
def new_project_page(
    client_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/ui/clients", status_code=302)
    return templates.TemplateResponse(request, "clients/new_project.html", {"user": user, "client": client})


@router.post("/clients/{client_id}/projects")
def create_project_web(
    client_id: str,
    request: Request,
    service_type: str = Form(...),
    scope_summary: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    p = Project(
        client_id=client_id,
        service_type=service_type,
        owner_id=user.id,
        scope_summary=scope_summary or None,
        gates={},
    )
    db.add(p)
    db.commit()
    return RedirectResponse(f"/ui/projects/{p.id}", status_code=302)


@router.get("/clients/{client_id}", response_class=HTMLResponse)
def client_detail_page(
    client_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/ui/clients", status_code=302)
    projects = (
        db.query(Project)
        .filter_by(client_id=client_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request, "clients/detail.html",
        {"user": user, "client": client, "projects": projects},
    )


@router.post("/clients/{client_id}")
def update_client_web(
    client_id: str,
    request: Request,
    entity_name: str = Form(...),
    sector: str = Form(""),
    regulatory_context: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/ui/clients", status_code=302)
    client.entity_name = entity_name
    client.sector = sector or None
    client.regulatory_context = regulatory_context or None
    db.commit()
    return RedirectResponse(f"/ui/clients/{client_id}", status_code=302)
