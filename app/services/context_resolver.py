"""Context resolver (Stage 19) — scopes EngagementCore context to a WorkMode.

Given (user_id, project_id, work_mode_name) the resolver:
  1. Loads the WorkMode (allowed_views + default_filters).
  2. Calls build_context_snapshot() to get the full project context.
  3. Filters to only the keys listed in allowed_views.
  4. Strips internal-only keys for client_contributor.
  5. Returns the scoped dict with work_mode + active_filters metadata.

Also provides persist_last_context / restore_last_context for re-login restore.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.workmode import (
    CLIENT_CONTRIBUTOR_STRIP_KEYS,
    UserLastContext,
    WorkMode,
    WorkModeName,
)


# ── Core resolver ─────────────────────────────────────────────────────────────

def resolve_context(
    db: Session,
    user_id: str,
    project_id: str,
    work_mode_name: str,
) -> dict:
    """Return a context dict scoped to the given work mode.

    Raises ValueError for unknown work_mode_name or missing project.
    """
    try:
        WorkModeName(work_mode_name)
    except ValueError:
        raise ValueError(f"Unknown work mode: {work_mode_name!r}")

    mode = db.query(WorkMode).filter_by(key=work_mode_name).first()
    if mode is None:
        raise ValueError(f"WorkMode {work_mode_name!r} not seeded in database")

    from app.engagementcore.context import build_context_snapshot
    full = build_context_snapshot(db, project_id)

    allowed = set(mode.allowed_views)
    scoped: dict = {k: v for k, v in full.items() if k in allowed}

    if work_mode_name == WorkModeName.client_contributor.value:
        for key in CLIENT_CONTRIBUTOR_STRIP_KEYS:
            scoped.pop(key, None)

    scoped["work_mode"] = work_mode_name
    scoped["active_filters"] = dict(mode.default_filters)
    return scoped


# ── Last-context persistence ───────────────────────────────────────────────────

def persist_last_context(
    db: Session,
    user_id: str,
    *,
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    work_mode_name: Optional[str] = None,
) -> UserLastContext:
    """Upsert the last-active context for a user."""
    record = db.query(UserLastContext).filter_by(user_id=user_id).first()
    if record is None:
        record = UserLastContext(user_id=user_id)
        db.add(record)
    if project_id is not None:
        record.project_id = project_id
    if client_id is not None:
        record.client_id = client_id
    if work_mode_name is not None:
        record.work_mode_name = work_mode_name
    db.flush()
    return record


def restore_last_context(db: Session, user_id: str) -> Optional[dict]:
    """Return the last-active context record for a user, or None if none saved."""
    record = db.query(UserLastContext).filter_by(user_id=user_id).first()
    if record is None:
        return None
    return {
        "user_id": record.user_id,
        "project_id": record.project_id,
        "client_id": record.client_id,
        "work_mode_name": record.work_mode_name,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


# ── Seed helper ───────────────────────────────────────────────────────────────

def seed_work_modes(db: Session) -> int:
    """Insert default WorkMode rows if they do not already exist. Returns count inserted."""
    from app.models.workmode import WORK_MODE_SEEDS
    inserted = 0
    for seed in WORK_MODE_SEEDS:
        exists = db.query(WorkMode).filter_by(key=seed["key"]).first()
        if exists is None:
            db.add(WorkMode(
                key=seed["key"],
                title=seed["title"],
                allowed_views=seed["allowed_views"],
                default_filters=seed["default_filters"],
            ))
            inserted += 1
    if inserted:
        db.flush()
    return inserted
