"""Telegram command handlers.

All mutating commands route through the audit/approval gateway.
No direct DB mutations outside of decide_approval / request_approval.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.db import SessionLocal
from app.models.clients import Project
from app.models.tasks import Task
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.audit import decide_approval

logger = logging.getLogger(__name__)

_BOT_ACTOR = "telegram-bot"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "TG Audit Orchestrator Bot\n\n"
        "/status <project_id> — project overview\n"
        "/approvals — list pending approvals\n"
        "/approve <id> — approve a request\n"
        "/reject <id> <reason> — reject with reason\n"
        "/tasks <project_id> — open tasks"
    )
    await update.message.reply_text(text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /status <project_id>")
        return

    project_id = args[0]
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            await update.message.reply_text(f"Project {project_id!r} not found.")
            return

        pending = (
            db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.project_id == project_id,
                ApprovalRequest.status == ApprovalStatus.pending,
            )
            .count()
        )
        open_tasks = (
            db.query(Task)
            .filter(Task.project_id == project_id, Task.status != "done")
            .count()
        )

        client_name = project.client.entity_name if project.client else "—"
        lines = [
            f"Project: {project_id}",
            f"Client:  {client_name}",
            f"Type:    {project.service_type}",
            f"Status:  {project.status}",
            f"Pending approvals: {pending}",
            f"Open tasks:        {open_tasks}",
        ]
        if project.scope_summary:
            lines.append(f"Scope:   {project.scope_summary[:120]}")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def cmd_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        pending = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.status == ApprovalStatus.pending)
            .order_by(ApprovalRequest.created_at)
            .limit(10)
            .all()
        )
        if not pending:
            await update.message.reply_text("No pending approvals.")
            return

        lines = ["Pending approvals (max 10):"]
        for ap in pending:
            lines.append(
                f"\nID: {ap.id[:8]}…\n"
                f"  Type:   {ap.target_type}\n"
                f"  Reason: {ap.reason[:80]}\n"
                f"  Role:   {ap.approver_role}\n"
                f"  Project:{ap.project_id}"
            )
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route through decide_approval — never bypasses the gateway."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /approve <approval_id>")
        return

    approval_id = args[0]
    db = SessionLocal()
    try:
        try:
            decide_approval(
                db,
                approval_id=approval_id,
                approved=True,
                decider_id=_BOT_ACTOR,
                reason="Approved via Telegram bot",
            )
            db.commit()
            await update.message.reply_text(f"Approved: {approval_id}")
        except ValueError as exc:
            db.rollback()
            await update.message.reply_text(f"Error: {exc}")
    finally:
        db.close()


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route through decide_approval — never bypasses the gateway."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /reject <approval_id> <reason>")
        return

    approval_id = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else "Rejected via Telegram bot"

    db = SessionLocal()
    try:
        try:
            decide_approval(
                db,
                approval_id=approval_id,
                approved=False,
                decider_id=_BOT_ACTOR,
                reason=reason,
            )
            db.commit()
            await update.message.reply_text(f"Rejected: {approval_id}")
        except ValueError as exc:
            db.rollback()
            await update.message.reply_text(f"Error: {exc}")
    finally:
        db.close()


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /tasks <project_id>")
        return

    project_id = args[0]
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            await update.message.reply_text(f"Project {project_id!r} not found.")
            return

        tasks = (
            db.query(Task)
            .filter(Task.project_id == project_id, Task.status != "done")
            .order_by(Task.due_date)
            .limit(15)
            .all()
        )
        if not tasks:
            await update.message.reply_text("No open tasks.")
            return

        lines = [f"Open tasks for {project_id} (max 15):"]
        for t in tasks:
            due = t.due_date.date() if t.due_date else "—"
            lines.append(f"\n• [{t.status}] {t.title}\n  Due: {due}")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()
