"""stage27_workflow_states

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-05 15:00:00.000000

Changes:
- Extend finding_status_enum with new states (draft, client_shared, remediation_planned,
  retest_pending, closed, risk_accepted)
- Extend deliverable_kind_enum with new kinds (retest_report, advisory_clinic_deck,
  management_summary, client_action_plan)
- Add is_released (Boolean, server_default=false) to deliverables
- Backfill: findings status open→in_review, remediated→closed, accepted→risk_accepted
- Backfill: tasks status open→planned
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_FINDING_STATUSES = [
    "open", "in_review", "approved", "remediated", "accepted",
]
_NEW_FINDING_STATUSES = [
    "draft", "in_review", "approved", "client_shared", "remediation_planned",
    "retest_pending", "closed", "risk_accepted",
    "open", "remediated", "accepted",
]

_OLD_DELIVERABLE_KINDS = [
    "gap_matrix", "roadmap", "report", "summary", "tracker",
]
_NEW_DELIVERABLE_KINDS = _OLD_DELIVERABLE_KINDS + [
    "retest_report", "advisory_clinic_deck", "management_summary", "client_action_plan",
]


def upgrade() -> None:
    # Extend finding_status_enum
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_OLD_FINDING_STATUSES, name="finding_status_enum"),
            type_=sa.Enum(*_NEW_FINDING_STATUSES, name="finding_status_enum"),
            existing_nullable=False,
        )

    # Extend deliverable_kind_enum
    with op.batch_alter_table("deliverables", schema=None) as batch_op:
        batch_op.alter_column(
            "kind",
            existing_type=sa.Enum(*_OLD_DELIVERABLE_KINDS, name="deliverable_kind_enum"),
            type_=sa.Enum(*_NEW_DELIVERABLE_KINDS, name="deliverable_kind_enum"),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column("is_released", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # Backfill: findings
    op.execute("UPDATE findings SET status='in_review' WHERE status='open'")
    op.execute("UPDATE findings SET status='closed' WHERE status='remediated'")
    op.execute("UPDATE findings SET status='risk_accepted' WHERE status='accepted'")

    # Backfill: tasks
    op.execute("UPDATE tasks SET status='planned' WHERE status='open'")


def downgrade() -> None:
    # Reverse backfill (best-effort — cannot recover original values)
    op.execute("UPDATE findings SET status='open' WHERE status='in_review'")
    op.execute("UPDATE findings SET status='remediated' WHERE status='closed'")
    op.execute("UPDATE findings SET status='accepted' WHERE status='risk_accepted'")
    op.execute("UPDATE tasks SET status='open' WHERE status='planned'")

    with op.batch_alter_table("deliverables", schema=None) as batch_op:
        batch_op.drop_column("is_released")
        batch_op.alter_column(
            "kind",
            existing_type=sa.Enum(*_NEW_DELIVERABLE_KINDS, name="deliverable_kind_enum"),
            type_=sa.Enum(*_OLD_DELIVERABLE_KINDS, name="deliverable_kind_enum"),
            existing_nullable=False,
        )

    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_NEW_FINDING_STATUSES, name="finding_status_enum"),
            type_=sa.Enum(*_OLD_FINDING_STATUSES, name="finding_status_enum"),
            existing_nullable=False,
        )
