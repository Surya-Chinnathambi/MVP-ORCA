"""RQ jobs for async notification delivery (Stage 22)."""
from __future__ import annotations

from typing import Optional


def deliver_notification(notification_id: str, channels: list[str]) -> None:
    """RQ job: deliver a Notification via the requested channels (email/telegram)."""
    from app.db import SessionLocal
    from app.models.notification import Notification

    db = SessionLocal()
    try:
        notif = db.get(Notification, notification_id)
        if notif is None:
            return
        recipient_email: Optional[str] = None
        chat_id: Optional[str] = None
        if notif.user:
            recipient_email = notif.user.email

        for channel in channels:
            if channel == "email" and recipient_email:
                from app.services.notifications.channels.email import send_email
                send_email(notif, recipient_email)
            elif channel == "telegram" and chat_id:
                from app.services.notifications.channels.telegram import send_telegram
                send_telegram(notif, chat_id)
    finally:
        db.close()


def send_deadline_reminder(evidence_request_id: str) -> None:
    """RQ job: fire a deadline reminder for an EvidenceRequest."""
    from app.db import SessionLocal
    from app.models.evidence import EvidenceRequest
    from app.services.notifications.triggers import on_evidence_request_deadline

    db = SessionLocal()
    try:
        on_evidence_request_deadline(db, evidence_request_id)
        db.commit()
    finally:
        db.close()
