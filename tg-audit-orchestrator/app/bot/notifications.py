"""Outbound Telegram notifications.

Call send_notification() from anywhere in the app to push a message.
If no bot token is configured, calls are silently skipped.

Notification kinds:
  approval_needed   — a new ApprovalRequest was created
  evidence_reminder — evidence request approaching due date
  deadline          — project / task deadline approaching
  finding_status    — a finding changed status
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level bot reference — set by start_bot() in run.py / lifespan.
_bot = None


def set_bot(bot) -> None:
    global _bot
    _bot = bot


def send_notification(chat_id: int | str, text: str) -> None:
    """Fire-and-forget notification. Silently skips if bot not configured."""
    if _bot is None:
        logger.debug("Bot not configured, skipping notification to %s", chat_id)
        return

    async def _send():
        try:
            await _bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            logger.exception("Failed to send Telegram notification to %s", chat_id)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send())
        else:
            loop.run_until_complete(_send())
    except RuntimeError:
        asyncio.run(_send())


def notify_approval_needed(
    chat_id: int | str,
    approval_id: str,
    target_type: str,
    reason: str,
    project_id: Optional[str] = None,
) -> None:
    text = (
        f"Approval needed\n"
        f"ID:      {approval_id[:8]}…\n"
        f"Type:    {target_type}\n"
        f"Reason:  {reason[:120]}\n"
        f"Project: {project_id or '—'}\n\n"
        f"Use /approve {approval_id} or /reject {approval_id} <reason>"
    )
    send_notification(chat_id, text)


def notify_evidence_reminder(
    chat_id: int | str,
    project_id: str,
    evidence_request_title: str,
    due_date: str,
) -> None:
    text = (
        f"Evidence reminder\n"
        f"Project: {project_id}\n"
        f"Request: {evidence_request_title}\n"
        f"Due:     {due_date}"
    )
    send_notification(chat_id, text)


def notify_deadline(
    chat_id: int | str,
    project_id: str,
    item_title: str,
    due_date: str,
) -> None:
    text = (
        f"Deadline approaching\n"
        f"Project: {project_id}\n"
        f"Item:    {item_title}\n"
        f"Due:     {due_date}"
    )
    send_notification(chat_id, text)


def notify_finding_status(
    chat_id: int | str,
    project_id: str,
    finding_id: str,
    finding_title: str,
    old_status: str,
    new_status: str,
) -> None:
    text = (
        f"Finding status changed\n"
        f"Project: {project_id}\n"
        f"Finding: {finding_title}\n"
        f"{old_status} → {new_status}\n"
        f"ID: {finding_id[:8]}…"
    )
    send_notification(chat_id, text)
