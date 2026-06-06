"""stageC4_approval_lifecycle

Revision ID: b0c1d2e3f4a5
Revises: a8b9c0d1e2f3
Create Date: 2026-06-06 13:00:00.000000

Changes (Full Spec §12 — 5-state approval lifecycle):
- Widen approval_status_enum to include: draft, requested, approved, rejected,
  applied, cancelled  (keeps 'pending' as legacy alias)
- Add applied_at (DateTime) and applied_by (FK→users) columns to approval_requests
- Backfill: 'pending' → 'requested'; 'approved' → 'applied' where change has been applied
  (conservative: only backfill 'approved' rows that have a decided_at stamp)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = ["pending", "approved", "rejected"]
_NEW_STATUSES = [
    "draft", "requested", "approved", "rejected", "applied", "cancelled",
    "pending",  # legacy alias retained for existing data
]


def upgrade() -> None:
    # 1. Widen the enum
    with op.batch_alter_table("approval_requests", schema=None) as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_OLD_STATUSES, name="approval_status_enum"),
            type_=sa.Enum(*_NEW_STATUSES, name="approval_status_enum"),
            existing_nullable=False,
        )
        # 2. Add new columns (no inline FK in batch mode — FK enforced at ORM layer)
        batch_op.add_column(sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("applied_by", sa.String(36), nullable=True))

    # 3. Backfill: 'pending' → 'requested'
    op.execute("UPDATE approval_requests SET status = 'requested' WHERE status = 'pending'")

    # 4. Backfill: 'approved' with decided_at → 'applied'
    #    (conservative — rows with decided_at have been acted upon)
    op.execute(
        "UPDATE approval_requests SET status = 'applied', applied_at = decided_at, applied_by = decided_by "
        "WHERE status = 'approved' AND decided_at IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("approval_requests", schema=None) as batch_op:
        batch_op.drop_column("applied_by")
        batch_op.drop_column("applied_at")
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_NEW_STATUSES, name="approval_status_enum"),
            type_=sa.Enum(*_OLD_STATUSES, name="approval_status_enum"),
            existing_nullable=False,
        )
