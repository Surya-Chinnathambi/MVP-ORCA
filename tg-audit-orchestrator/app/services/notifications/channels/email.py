"""Email channel — smtplib sender (Stage 22).

SMTP credentials come entirely from .env via settings:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
Never hard-coded here.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Optional

from app.models.notification import Notification


def send_email(notification: Notification, recipient_email: str) -> None:
    """Send notification as a plain-text email via SMTP.

    Silently no-ops if SMTP_HOST is not configured (dev environment).
    """
    from app.config import settings
    host = getattr(settings, "smtp_host", "")
    if not host:
        return

    port = getattr(settings, "smtp_port", 587)
    user = getattr(settings, "smtp_user", "")
    password = getattr(settings, "smtp_password", "")
    from_addr = getattr(settings, "smtp_from", user)

    subject = f"[TG Audit] {notification.kind.replace('_', ' ').title()}"
    body = notification.message or str(notification.payload or "")

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP(host, int(port)) as server:
            if user:
                server.starttls()
                server.login(user, password)
            server.sendmail(from_addr, [recipient_email], msg.as_string())
    except Exception:
        pass  # delivery failure is non-fatal
