"""stage19_work_modes

Revision ID: d564468c133e
Revises: e2336deb3216
Create Date: 2026-06-05 10:54:03.035066

Changes:
- Create work_modes table and seed the 5 standard modes
- Create user_last_contexts table (one row per user, upserted on activity)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd564468c133e'
down_revision: Union[str, None] = 'e2336deb3216'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

import json
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SEEDS = [
    {
        "name": "pm",
        "display_name": "Project Manager",
        "allowed_views": json.dumps(["phase", "open_tasks", "pending_approvals",
                                      "pending_evidence_requests", "progress", "gates", "active_pack"]),
        "default_filters": json.dumps({"task_status": "open"}),
    },
    {
        "name": "analyst",
        "display_name": "Analyst",
        "allowed_views": json.dumps(["phase", "open_tasks", "pending_evidence_requests",
                                      "progress", "active_pack", "findings", "evidence_items", "scope_items"]),
        "default_filters": json.dumps({"finding_status": "open"}),
    },
    {
        "name": "reviewer",
        "display_name": "Reviewer",
        "allowed_views": json.dumps(["phase", "findings", "evidence_items", "deliverables", "progress", "gates"]),
        "default_filters": json.dumps({"evidence_reviewer_status": "pending"}),
    },
    {
        "name": "deliverable_builder",
        "display_name": "Deliverable Builder",
        "allowed_views": json.dumps(["phase", "deliverables", "progress", "gates",
                                      "findings", "evidence_items", "active_pack"]),
        "default_filters": json.dumps({"evidence_lifecycle_state": "classified"}),
    },
    {
        "name": "client_contributor",
        "display_name": "Client Contributor",
        "allowed_views": json.dumps(["phase", "open_tasks", "pending_evidence_requests"]),
        "default_filters": json.dumps({"task_assigned_to_user": True}),
    },
]


def upgrade() -> None:
    op.create_table(
        'work_modes',
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('allowed_views', sa.JSON(), nullable=False),
        sa.Column('default_filters', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'user_last_contexts',
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('client_id', sa.String(36), nullable=True),
        sa.Column('work_mode_name', sa.String(50), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # Seed the 5 standard work modes
    now = _now()
    work_modes_table = sa.table(
        'work_modes',
        sa.column('id', sa.String),
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('allowed_views', sa.String),
        sa.column('default_filters', sa.String),
        sa.column('created_at', sa.String),
        sa.column('updated_at', sa.String),
    )
    op.bulk_insert(work_modes_table, [
        {
            "id": str(uuid.uuid4()),
            "name": s["name"],
            "display_name": s["display_name"],
            "allowed_views": s["allowed_views"],
            "default_filters": s["default_filters"],
            "created_at": now,
            "updated_at": now,
        }
        for s in _SEEDS
    ])


def downgrade() -> None:
    op.drop_table('user_last_contexts')
    op.drop_table('work_modes')
