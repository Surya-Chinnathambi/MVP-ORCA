"""Notification dispatch (Stage 22).

notify() is the single entry point:
  - Always writes a Notification row to DB (web inbox — synchronous).
  - Optionally enqueues email / Telegram delivery via RQ.
  - Filters payload for client_contributor recipients (strips internal-only keys).

_get_queue() returns the RQ Queue; tests override via monkeypatch or is_async=False.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.notification import (
    INTERNAL_ONLY_PAYLOAD_KEYS,
    Notification,
    NotificationChannel,
)

# ── Queue factory (tests monkeypatch this) ────────────────────────────────────

def _get_queue():
    from redis import Redis
    from rq import Queue
    from app.config import settings
    conn = Redis.from_url(settings.redis_url)
    return Queue(connection=conn)


# ── Payload filtering ─────────────────────────────────────────────────────────

def _is_client_contributor(db: Session, user_id: str) -> bool:
    """Return True if the user's highest role is client_contributor."""
    from app.models.users import Permission, Role
    perm = (
        db.query(Permission)
        .join(Role, Role.id == Permission.role_id)
        .filter(
            Permission.user_id == user_id,
            Role.name == "client_contributor",
        )
        .first()
    )
    return perm is not None


def filter_payload(payload: dict, is_contributor: bool) -> dict:
    """Strip internal-only keys from payload for client_contributor recipients."""
    if not is_contributor or not payload:
        return payload or {}
    return {k: v for k, v in payload.items() if k not in INTERNAL_ONLY_PAYLOAD_KEYS}


# ── Core dispatcher ───────────────────────────────────────────────────────────

def notify(
    db: Session,
    user_id: str,
    event_type: str,
    payload: Optional[dict] = None,
    *,
    project_id: Optional[str] = None,
    message: Optional[str] = None,
    channels: Optional[list[str]] = None,
) -> Notification:
    """Create a web Notification and optionally enqueue async channel delivery.

    channels defaults to ["web"]. Additional values: "email", "telegram".
    The payload is filtered for client_contributor recipients before storage.
    """
    if channels is None:
        channels = [NotificationChannel.web.value]

    is_contrib = _is_client_contributor(db, user_id)
    safe_payload = filter_payload(payload or {}, is_contrib)

    notif = Notification(
        user_id=user_id,
        event_type=event_type,
        channel=NotificationChannel.web.value,
        payload=safe_payload,
        project_id=project_id,
        message=message,
        is_read=False,
    )
    db.add(notif)
    db.flush()

    # Enqueue async delivery for non-web channels
    extra = [c for c in channels if c != NotificationChannel.web.value]
    if extra:
        try:
            q = _get_queue()
            from app.services.notifications import jobs as notif_jobs
            q.enqueue(notif_jobs.deliver_notification, notif.id, extra)
        except Exception:
            pass  # delivery failure must never block the caller

    return notif
