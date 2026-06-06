"""stage14: org tenant + engagementcore skeleton

Revision ID: a6513e362bf9
Revises: 87b2c02867fc
Create Date: 2026-06-05

Changes:
  - Create organizations table
  - Add organization_id (nullable FK) to clients; backfill a single 'Tech Guard' org
  - Create engagement_states table (1:1 with projects)
  - Create engagement_objectives table (N:1 with projects)
  - Backfill one EngagementState per existing project, phase from status
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "a6513e362bf9"
down_revision: Union[str, None] = "87b2c02867fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_phase(status: str) -> str:
    mapping = {
        "setup": "setup", "draft": "setup",
        "active": "active", "scoped": "active",
        "review": "review", "in_review": "review",
        "closed": "closed", "archived": "closed",
    }
    return mapping.get(status, "setup")


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create organizations ───────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 2. Add organization_id to clients ─────────────────────────────────────
    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(
            sa.Column("organization_id", sa.String(36), nullable=True)
        )

    # ── 3. Backfill: insert default org + assign all clients ──────────────────
    now = _utcnow()
    default_org_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO organizations (id, name, display_name, created_at, updated_at) "
            "VALUES (:id, :name, :dn, :ca, :ua)"
        ),
        {"id": default_org_id, "name": "Tech Guard", "dn": "TechGuard Labs",
         "ca": now, "ua": now},
    )
    conn.execute(
        text("UPDATE clients SET organization_id = :org_id"),
        {"org_id": default_org_id},
    )

    # ── 4. Create engagement_states ───────────────────────────────────────────
    op.create_table(
        "engagement_states",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("phase", sa.String(50), nullable=False, server_default="setup"),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("blockers", sa.JSON(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_engagement_state_project"),
    )

    # ── 5. Create engagement_objectives ──────────────────────────────────────
    op.create_table(
        "engagement_objectives",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("depends_on", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("linked_requirement_ids", sa.JSON(), nullable=True),
        sa.Column("linked_evidence_ids", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 6. Backfill: one EngagementState per existing project ─────────────────
    projects = conn.execute(text("SELECT id, status FROM projects")).fetchall()
    for row in projects:
        pid, status = row[0], row[1]
        phase = _derive_phase(status or "setup")
        es_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO engagement_states "
                "(id, project_id, phase, created_at, updated_at) "
                "VALUES (:id, :pid, :phase, :ca, :ua)"
            ),
            {"id": es_id, "pid": pid, "phase": phase, "ca": now, "ua": now},
        )


def downgrade() -> None:
    op.drop_table("engagement_objectives")
    op.drop_table("engagement_states")
    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_column("organization_id")
    op.drop_table("organizations")
