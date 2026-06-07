"""Web-layer dependencies: auth, role checks, and project access guards."""
from typing import List, Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import Permission, Role, RoleName, User

LOGIN_REDIRECT = RedirectResponse("/ui/login", status_code=302)
FORBIDDEN_REDIRECT = RedirectResponse("/ui/forbidden", status_code=302)

# Role hierarchy: higher number = more privilege
_ROLE_LEVEL = {
    RoleName.platform_admin: 10,
    RoleName.partner: 9,
    RoleName.pm: 8,
    RoleName.lead_consultant: 7,
    RoleName.analyst: 6,
    RoleName.senior_reviewer: 5,
    RoleName.qa: 4,
    RoleName.client_approver: 3,
    RoleName.client_contributor: 2,
    RoleName.readonly: 1,
}


def get_web_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    uid: Optional[str] = request.session.get("user_id")
    if not uid:
        return None
    user = db.get(User, uid)
    return user if (user and user.is_active) else None


def get_user_roles(user: User, db: Session, scope_id: Optional[str] = None) -> List[str]:
    """Return all role name strings this user holds, optionally scoped."""
    q = (
        db.query(Role.name)
        .join(Permission, Permission.role_id == Role.id)
        .filter(Permission.user_id == user.id)
    )
    if scope_id:
        q = q.filter(
            (Permission.scope_id == scope_id) | (Permission.scope_id.is_(None))
        )
    return [row[0] for row in q.all()]


def user_has_any_role(
    user: User,
    db: Session,
    required: List[str],
    scope_id: Optional[str] = None,
) -> bool:
    """True if user holds at least one of the required roles (or is platform_admin)."""
    roles = get_user_roles(user, db, scope_id)
    if RoleName.platform_admin in roles:
        return True
    return any(r in roles for r in required)


def _fresh_install(db: Session) -> bool:
    """True when no permissions have been assigned yet (first-run grace period)."""
    return db.query(Permission).count() == 0


def require_admin_role(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_web_user),
):
    """Dependency: require platform_admin or partner role. Redirects on failure."""
    if user is None:
        return None  # caller will handle LOGIN_REDIRECT
    if _fresh_install(db):
        return user  # no roles assigned yet — allow first-time setup
    if user_has_any_role(user, db, [RoleName.platform_admin, RoleName.partner]):
        return user
    return None  # caller treats None as forbidden


def can_approve(user: User, approver_role: str, db: Session, project_id: Optional[str] = None) -> bool:
    """True if user's assigned roles include the required approver_role."""
    if not user:
        return False
    roles = get_user_roles(user, db, scope_id=project_id)
    if RoleName.platform_admin in roles:
        return True
    # partner can approve anything
    if RoleName.partner in roles:
        return True
    return approver_role in roles


def get_highest_role(user: User, db: Session) -> Optional[str]:
    """Return the highest-privilege role name this user holds."""
    roles = get_user_roles(user, db)
    if not roles:
        return None
    return max(roles, key=lambda r: _ROLE_LEVEL.get(r, 0))


def base_ctx(user: Optional[User], db: Session) -> dict:
    """Base template context injected into every page that extends base.html."""
    return {
        "user": user,
        "user_highest_role": get_highest_role(user, db) if user else None,
    }
