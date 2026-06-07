"""Web views — Per-project team management."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.clients import Project
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.web.deps import LOGIN_REDIRECT, base_ctx, get_highest_role, get_web_user

router = APIRouter(tags=["web-team"])
templates = Jinja2Templates(directory="app/web/templates")

# Roles that can manage project team membership
_MANAGE_ROLES = {RoleName.platform_admin, RoleName.partner, RoleName.pm}

# What each role can do within a project (shown in capabilities section)
ROLE_CAPABILITIES: dict[str, list[str]] = {
    "platform_admin":     ["Full platform access — all operations"],
    "partner":            ["Full access to all client projects"],
    "pm":                 ["Manage team, approve gates, assign tasks, create evidence requests"],
    "lead_consultant":    ["Run all scan phases, create/review findings, generate report pack"],
    "analyst":            ["Run analyst scan phases, upload evidence, log draft findings"],
    "senior_reviewer":    ["Review & approve findings, approve evidence, sign off G4 gate"],
    "qa":                 ["Quality check findings & report draft, sign off G5 gate"],
    "client_approver":    ["View final report, approve deliverables, sign G7 closure"],
    "client_contributor": ["Upload client evidence, answer intake questionnaire"],
    "readonly":           ["View-only access to project data"],
}

# Role display order for config block
_ROLE_ORDER = [
    "pm", "lead_consultant", "analyst", "senior_reviewer",
    "qa", "client_approver", "client_contributor", "readonly",
]


def _get_project_team(db: Session, project_id: str) -> list[dict]:
    """Return all project-scoped permissions for a project, enriched with user/role info."""
    rows = (
        db.query(Permission, User, Role)
        .join(User, Permission.user_id == User.id)
        .join(Role, Permission.role_id == Role.id)
        .filter(Permission.scope_level == ScopeLevel.project)
        .filter(Permission.scope_id == project_id)
        .order_by(Role.name, User.full_name)
        .all()
    )
    return [
        {
            "perm_id": perm.id,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": role.name,
            "assigned_at": perm.created_at,
        }
        for perm, user, role in rows
    ]


def _build_conf(members: list[dict]) -> str:
    """Generate an INI-style project config block from the team roster."""
    by_role: dict[str, list[str]] = {}
    for m in members:
        role = m["role"].value if hasattr(m["role"], "value") else str(m["role"])
        by_role.setdefault(role, []).append(m["email"])

    lines = ["[team]"]
    for role in _ROLE_ORDER:
        if role in by_role:
            lines.append(f"{role} = {', '.join(by_role[role])}")
    for role, emails in sorted(by_role.items()):
        if role not in _ROLE_ORDER:
            lines.append(f"{role} = {', '.join(emails)}")
    return "\n".join(lines)


@router.get("/projects/{project_id}/team", response_class=HTMLResponse)
def team_page(
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

    highest = get_highest_role(user, db)
    role_str = highest.value if hasattr(highest, "value") else str(highest or "")
    can_manage = highest in _MANAGE_ROLES

    members = _get_project_team(db, project_id)
    conf_block = _build_conf(members)

    # Users not yet in the project team (available to add)
    assigned_ids = {m["user_id"] for m in members}
    all_users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
    available_users = [u for u in all_users if u.id not in assigned_ids]

    all_roles = db.query(Role).order_by(Role.name).all()

    return templates.TemplateResponse(
        request, "projects/team.html",
        {
            **base_ctx(user, db),
            "project": project,
            "members": members,
            "conf_block": conf_block,
            "can_manage": can_manage,
            "available_users": available_users,
            "all_roles": all_roles,
            "role_capabilities": ROLE_CAPABILITIES,
            "role_order": _ROLE_ORDER,
        },
    )


@router.post("/projects/{project_id}/team/add")
def add_team_member(
    project_id: str,
    request: Request,
    user_id: str = Form(...),
    role_name: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    highest = get_highest_role(user, db)
    if highest not in _MANAGE_ROLES:
        return RedirectResponse("/ui/forbidden", status_code=302)

    project = db.get(Project, project_id)
    target_user = db.get(User, user_id)
    if not project or not target_user:
        return RedirectResponse(f"/ui/projects/{project_id}/team", status_code=302)

    # Find or validate role
    role = db.query(Role).filter_by(name=role_name).first()
    if not role:
        return RedirectResponse(f"/ui/projects/{project_id}/team", status_code=302)

    # Upsert: if user already has a project-scoped perm, update the role
    existing = (
        db.query(Permission)
        .filter_by(scope_level=ScopeLevel.project, scope_id=project_id, user_id=user_id)
        .first()
    )
    if existing:
        existing.role_id = role.id
    else:
        db.add(Permission(
            user_id=user_id,
            role_id=role.id,
            scope_level=ScopeLevel.project,
            scope_id=project_id,
        ))
    db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/team", status_code=302)


@router.post("/projects/{project_id}/team/remove/{perm_id}")
def remove_team_member(
    project_id: str,
    perm_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    if user is None:
        return LOGIN_REDIRECT
    highest = get_highest_role(user, db)
    if highest not in _MANAGE_ROLES:
        return RedirectResponse("/ui/forbidden", status_code=302)

    perm = db.get(Permission, perm_id)
    if perm and perm.scope_level == ScopeLevel.project and perm.scope_id == project_id:
        db.delete(perm)
        db.commit()
    return RedirectResponse(f"/ui/projects/{project_id}/team", status_code=302)
