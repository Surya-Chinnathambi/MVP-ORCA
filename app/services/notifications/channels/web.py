"""Web channel — notification already in DB, just mark channel."""
from app.models.notification import Notification, NotificationChannel


def send_web(notification: Notification) -> None:
    """No-op: web notifications are written synchronously by dispatch.notify()."""
    notification.channel = NotificationChannel.web.value
