"""Telegram bot entry point.

Token is read from settings.telegram_bot_token.
The bot never bypasses the approval gateway — all approve/reject actions
route through services.audit.decide_approval.

Run standalone: python -m app.bot.run
Or start via lifespan from main.py.
"""
import logging

from telegram import BotCommand
from telegram.ext import Application, CommandHandler

from app.bot.commands import (
    cmd_approve,
    cmd_approvals,
    cmd_reject,
    cmd_start,
    cmd_status,
    cmd_tasks,
)

logger = logging.getLogger(__name__)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("approvals", cmd_approvals))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("tasks", cmd_tasks))

    return app


async def set_bot_commands(application: Application) -> None:
    commands = [
        BotCommand("start", "Show help"),
        BotCommand("status", "/status <project_id> — project status"),
        BotCommand("approvals", "List pending approvals"),
        BotCommand("approve", "/approve <id> — approve a request"),
        BotCommand("reject", "/reject <id> <reason> — reject a request"),
        BotCommand("tasks", "/tasks <project_id> — list open tasks"),
    ]
    await application.bot.set_my_commands(commands)
