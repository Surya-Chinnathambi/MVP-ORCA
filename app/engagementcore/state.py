"""EngagementState service — read, update, and auto-create.

The auto-create listener fires after every Project insert so every project
always has exactly one EngagementState row.

Phase derivation from project status:
  setup / draft        → setup
  active / scoped      → active
  review / in_review   → review
  closed / archived    → closed
  anything else        → setup
"""
from typing import Any, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.engagement import EngagementState


# ── Phase helper ─────────────────────────────────────────────────────────────

def _derive_phase(project_status: str) -> str:
    mapping = {
        "setup": "setup",
        "draft": "setup",
        "active": "active",
        "scoped": "active",
        "review": "review",
        "in_review": "review",
        "closed": "closed",
        "archived": "closed",
    }
    return mapping.get(project_status, "setup")


# ── Auto-create listeners (deferred two-step) ─────────────────────────────────
# We use two events to avoid calling session.add() during the flush execution
# stage (which triggers a SAWarning).
#
# Step 1 — after_insert (mapper event, fires during flush): mark project id.
# Step 2 — after_flush  (session event, fires after execution): add the row.

def _mark_project_for_state(mapper, connection, target) -> None:
    session = Session.object_session(target)
    if session is not None:
        session.info.setdefault("_pending_es_project_ids", []).append(
            (target.id, target.status)
        )


def _create_deferred_states(session, flush_context) -> None:
    pending = session.info.pop("_pending_es_project_ids", [])
    for pid, status in pending:
        existing = session.query(EngagementState).filter_by(project_id=pid).first()
        if existing is None:
            session.add(EngagementState(
                project_id=pid,
                phase=_derive_phase(status or "setup"),
                progress={},
                blockers=[],
                context_snapshot={},
            ))


def register_listeners() -> None:
    """Wire up listeners. Called once from app/models/__init__.py."""
    from app.models.clients import Project
    event.listen(Project, "after_insert", _mark_project_for_state)
    event.listen(Session, "after_flush", _create_deferred_states)


# ── Service functions ─────────────────────────────────────────────────────────

def get_state(db: Session, project_id: str) -> Optional[EngagementState]:
    return db.query(EngagementState).filter_by(project_id=project_id).first()


def update_state(
    db: Session,
    project_id: str,
    *,
    phase: Optional[str] = None,
    progress: Optional[Any] = None,
    blockers: Optional[Any] = None,
    context_snapshot: Optional[Any] = None,
) -> EngagementState:
    state = get_state(db, project_id)
    if state is None:
        raise ValueError(f"No EngagementState for project {project_id!r}")
    if phase is not None:
        state.phase = phase
    if progress is not None:
        state.progress = progress
    if blockers is not None:
        state.blockers = blockers
    if context_snapshot is not None:
        state.context_snapshot = context_snapshot
    return state
