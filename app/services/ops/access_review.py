"""Access review — generate a permission report for periodic review.

The report lists every (user, role, scope) triple so a partner or
platform_admin can audit who has access to what.  Can be run as an
RQ job (scheduled weekly) or called directly as a service function.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def generate_access_report(db_url: str) -> dict[str, Any]:
    """Query permissions and return a structured report dict.

    Creates its own DB session so the function can run as an RQ job
    without inheriting the caller's session.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models.users import Permission, Role, User

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    with Session(engine) as db:
        rows = (
            db.query(Permission, User, Role)
            .join(User, User.id == Permission.user_id)
            .join(Role, Role.id == Permission.role_id)
            .order_by(User.email, Role.name)
            .all()
        )

        permissions = []
        role_counts: dict[str, int] = {}
        user_ids: set[str] = set()

        for perm, user, role in rows:
            permissions.append({
                "user_id": user.id,
                "user_email": user.email,
                "user_full_name": user.full_name,
                "role": role.name,
                "scope_level": perm.scope_level,
                "scope_id": perm.scope_id,
                "is_active": user.is_active,
            })
            role_counts[role.name] = role_counts.get(role.name, 0) + 1
            user_ids.add(user.id)

    engine.dispose()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_users": len(user_ids),
        "total_permissions": len(permissions),
        "permissions": permissions,
        "summary": {
            "roles": role_counts,
        },
    }


def run_access_review_job(db_url: str) -> dict[str, Any]:
    """RQ job entry point — same as generate_access_report."""
    return generate_access_report(db_url)
