"""stageC3_workflow_defaults

Revision ID: a8b9c0d1e2f3
Revises: f5a6b7c8d9e0
Create Date: 2026-06-06 12:00:00.000000

Changes:
- tasks.status: String(50) → Enum(task_status_enum); backfill 'open' → 'planned'
- projects.status: String(50) → Enum(project_status_enum); backfill 'setup' → 'draft'
- Finding.status default now 'draft' (Python-level only; enum column already correct)
- EngagementState.phase default now 'draft' (Python-level only)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK_STATUSES = [
    "planned", "assigned", "in_progress", "blocked", "review", "complete", "cancelled",
]

_PROJECT_STATUSES = [
    "draft", "scoped", "active", "review", "client_review", "final", "closed", "archived",
    "setup",  # legacy value retained for backfill; never a creation default
]


def upgrade() -> None:
    # ── tasks.status: String → Enum, backfill open→planned ───────────────────
    # Backfill first so no invalid values enter the new enum
    op.execute("UPDATE tasks SET status = 'planned' WHERE status = 'open'")

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(50),
            type_=sa.Enum(*_TASK_STATUSES, name="task_status_enum"),
            existing_nullable=False,
            existing_server_default=None,
        )

    # ── projects.status: String → Enum, backfill setup→draft ─────────────────
    op.execute("UPDATE projects SET status = 'draft' WHERE status = 'setup'")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(50),
            type_=sa.Enum(*_PROJECT_STATUSES, name="project_status_enum"),
            existing_nullable=False,
            existing_server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_PROJECT_STATUSES, name="project_status_enum"),
            type_=sa.String(50),
            existing_nullable=False,
        )

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_TASK_STATUSES, name="task_status_enum"),
            type_=sa.String(50),
            existing_nullable=False,
        )
