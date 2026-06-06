"""Notifications API — web inbox for the current user (Stage 22)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.notification import Notification, NotificationStatus
from app.models.users import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's web-channel notifications, newest first."""
    q = db.query(Notification).filter_by(recipient_user_id=current_user.id)
    if unread_only:
        q = q.filter(Notification.status != NotificationStatus.read.value)
    items = q.order_by(Notification.created_at.desc()).limit(50).all()
    return [
        {
            "id": n.id,
            "kind": n.kind,
            "message": n.message,
            "payload": n.payload,
            "status": n.status,
            "project_id": n.project_id,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read."""
    notif = db.get(Notification, notification_id)
    if notif is None or notif.recipient_user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.status = NotificationStatus.read.value
    db.commit()
    return {"id": notification_id, "status": "read"}


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all web-channel notifications as read for the current user."""
    db.query(Notification).filter(
        Notification.recipient_user_id == current_user.id,
        Notification.status != NotificationStatus.read.value,
    ).update({"status": NotificationStatus.read.value})
    db.commit()
    return {"marked_read": True}
