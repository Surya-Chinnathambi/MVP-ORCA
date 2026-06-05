"""FastAPI dependency factories for auth + permission enforcement."""
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.users import Permission, Role, RoleName, User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id: Optional[str] = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(role_name: str) -> Callable:
    """Return a dependency that enforces the caller holds the given role."""

    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role = db.query(Role).filter_by(name=role_name).first()
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not found")
        perm = (
            db.query(Permission)
            .filter_by(user_id=current_user.id, role_id=role.id)
            .first()
        )
        if perm is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {role_name}",
            )
        return current_user

    return _check


def require_project_access(project_id: str, role_name: str, db: Session, user: User) -> bool:
    """Check user has the given role scoped to a specific project (or globally)."""
    role = db.query(Role).filter_by(name=role_name).first()
    if role is None:
        return False
    perm = (
        db.query(Permission)
        .filter(
            Permission.user_id == user.id,
            Permission.role_id == role.id,
            (Permission.scope_id == project_id) | (Permission.scope_id.is_(None)),
        )
        .first()
    )
    return perm is not None


def check_evidence_access(item, user: User, db: Session) -> bool:
    """Return True if user may access a restricted EvidenceItem.

    Non-restricted items are always accessible.
    Restricted items require an evidence_item or organization scope-level Permission.
    """
    if not getattr(item, "is_restricted", False):
        return True
    from app.models.users import ScopeLevel
    ALLOWED = {ScopeLevel.evidence_item.value, ScopeLevel.organization.value}
    perms = (
        db.query(Permission)
        .filter(
            Permission.user_id == user.id,
            Permission.scope_level.in_(ALLOWED),
        )
        .all()
    )
    for perm in perms:
        if perm.scope_id is None or perm.scope_id == str(item.id):
            return True
    return False


# Common pre-built dependency aliases
require_admin = require_role(RoleName.admin.value)
