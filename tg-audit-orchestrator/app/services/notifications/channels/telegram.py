"""Telegram channel — reuses Stage 12 bot token (Stage 22).

Bot token comes from settings.telegram_bot_token (.env only).
chat_id is resolved from user profile or a platform-level mapping.
Silently no-ops if no token is configured.
"""
from __future__ import annotations

from app.models.notification import Notification


def send_telegram(notification: Notification, chat_id: str) -> None:
    """Send notification as a Telegram message using the Stage 12 bot token.

    Uses python-telegram-bot in sync mode (Bot.send_message via asyncio.run).
    No-ops if telegram_bot_token is not configured.
    """
    from app.config import settings
    token = settings.telegram_bot_token
    if not token or not chat_id:
        return

    text = notification.message or (
        f"[{notification.kind}] {notification.payload or ''}"
    )

    try:
        import asyncio
        from telegram import Bot  # type: ignore
        bot = Bot(token=token)
        asyncio.run(bot.send_message(chat_id=chat_id, text=text[:4096]))
    except Exception:
        pass  # delivery failure is non-fatal
