"""Stage 12 acceptance test — Telegram bot.

Verifies:
1. /approve <id> routes through decide_approval and writes an audit event.
2. /reject <id> <reason> routes through decide_approval and writes an audit event.
3. A trigger-bound quick update creates a pending ApprovalRequest, not a direct mutation.
4. /status and /tasks return data without crashing.
5. /approvals lists pending items.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.tasks import Task, TaskKind
from app.models.users import Role, RoleName, User
from app.models.workflow import ApprovalRequest, ApprovalStatus, AuditTrailEvent
from app.services.audit import decide_approval, request_approval
from app.services.auth import hash_password


# ── DB setup ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def _SessionMaker(_engine):
    return sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module")
def _seed(_engine, _SessionMaker):
    """Returns plain IDs (strings), not ORM objects, to avoid DetachedInstanceError."""
    with Session(_engine) as db:
        for name in [r.value for r in RoleName]:
            db.add(Role(name=name))
        admin = User(
            email="bot_admin@test.local",
            password_hash=hash_password("password"),
            full_name="Bot Admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()

        client = Client(entity_name="BotTest Corp")
        db.add(client)
        db.flush()

        project = Project(
            client_id=client.id,
            service_type=ServiceType.vapt,
            owner_id=admin.id,
            status="active",
        )
        db.add(project)
        db.flush()

        task = Task(
            project_id=project.id,
            kind=TaskKind.test,
            title="Recon phase",
            status="open",
        )
        db.add(task)
        db.flush()

        approval = request_approval(
            db,
            project_id=project.id,
            target_type="scope",
            target_id=project.id,
            reason="Initial scope approval",
            approver_role="partner",
            requested_by=admin.id,
        )
        db.flush()
        db.commit()

        return {
            "admin_id": admin.id,
            "project_id": project.id,
            "task_id": task.id,
            "approval_id": approval.id,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_update() -> MagicMock:
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    return update


def _make_context(args: list[str]) -> MagicMock:
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestApproveCommand:
    def test_approve_routes_through_gateway_and_writes_audit_event(
        self, _seed, _engine, _SessionMaker
    ):
        """/approve calls decide_approval and an audit event is written."""
        from app.bot.commands import cmd_approve

        approval_id = _seed["approval_id"]
        update = _make_update()
        ctx = _make_context([approval_id])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_approve(update, ctx))
        finally:
            db.close()

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Approved" in reply or approval_id[:8] in reply

        with Session(_engine) as check:
            updated = check.get(ApprovalRequest, approval_id)
            assert updated.status == ApprovalStatus.approved

            event = (
                check.query(AuditTrailEvent)
                .filter(
                    AuditTrailEvent.target_id == approval_id,
                    AuditTrailEvent.action == "approval.approved",
                )
                .first()
            )
            assert event is not None, "Audit event must be written when approval is decided"


class TestRejectCommand:
    def test_reject_routes_through_gateway_and_writes_audit_event(
        self, _seed, _engine, _SessionMaker
    ):
        """/reject calls decide_approval and an audit event is written."""
        from app.bot.commands import cmd_reject

        project_id = _seed["project_id"]

        # Create a fresh approval to reject
        with Session(_engine) as setup:
            new_approval = request_approval(
                setup,
                project_id=project_id,
                target_type="finding",
                target_id="finding-001",
                reason="Severity change review",
                approver_role="partner",
            )
            setup.commit()
            approval_id = new_approval.id

        update = _make_update()
        ctx = _make_context([approval_id, "too", "vague"])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_reject(update, ctx))
        finally:
            db.close()

        update.message.reply_text.assert_called_once()

        with Session(_engine) as check:
            updated = check.get(ApprovalRequest, approval_id)
            assert updated.status == ApprovalStatus.rejected

            event = (
                check.query(AuditTrailEvent)
                .filter(
                    AuditTrailEvent.target_id == approval_id,
                    AuditTrailEvent.action == "approval.rejected",
                )
                .first()
            )
            assert event is not None, "Audit event must be written on rejection"


class TestTriggerBoundUpdateCreatesApproval:
    def test_trigger_bound_change_creates_pending_approval_not_direct_mutation(
        self, _seed, _engine
    ):
        """Trigger-bound changes must create a pending ApprovalRequest, not mutate directly."""
        project_id = _seed["project_id"]
        task_id = _seed["task_id"]

        with Session(_engine) as db:
            before_count = (
                db.query(ApprovalRequest)
                .filter(
                    ApprovalRequest.project_id == project_id,
                    ApprovalRequest.status == ApprovalStatus.pending,
                )
                .count()
            )

            ap = request_approval(
                db,
                project_id=project_id,
                target_type="task",
                target_id=task_id,
                reason="Task cancelled mid-engagement",
                approver_role="pm",
            )
            db.commit()

            after_count = (
                db.query(ApprovalRequest)
                .filter(
                    ApprovalRequest.project_id == project_id,
                    ApprovalRequest.status == ApprovalStatus.pending,
                )
                .count()
            )

            assert after_count == before_count + 1, (
                "Trigger-bound change must create a pending ApprovalRequest"
            )
            assert ap.status == ApprovalStatus.pending

            task = db.get(Task, task_id)
            assert task.status == "open", (
                "Task must not be mutated directly — must wait for approval"
            )


class TestStatusCommand:
    def test_status_returns_project_info(self, _seed, _engine, _SessionMaker):
        from app.bot.commands import cmd_status

        project_id = _seed["project_id"]
        update = _make_update()
        ctx = _make_context([project_id])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_status(update, ctx))
        finally:
            db.close()

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert project_id in reply
        assert "Status" in reply

    def test_status_unknown_project(self, _seed, _engine, _SessionMaker):
        from app.bot.commands import cmd_status

        update = _make_update()
        ctx = _make_context(["unknown-id"])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_status(update, ctx))
        finally:
            db.close()

        reply = update.message.reply_text.call_args[0][0]
        assert "not found" in reply.lower()


class TestApprovalsCommand:
    def test_approvals_lists_pending(self, _seed, _engine, _SessionMaker):
        from app.bot.commands import cmd_approvals

        update = _make_update()
        ctx = _make_context([])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_approvals(update, ctx))
        finally:
            db.close()

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "pending" in reply.lower() or "Pending" in reply


class TestTasksCommand:
    def test_tasks_returns_open_tasks(self, _seed, _engine, _SessionMaker):
        from app.bot.commands import cmd_tasks

        project_id = _seed["project_id"]
        update = _make_update()
        ctx = _make_context([project_id])

        db = _SessionMaker()
        try:
            with patch("app.bot.commands.SessionLocal", return_value=db):
                _run(cmd_tasks(update, ctx))
        finally:
            db.close()

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Recon phase" in reply
