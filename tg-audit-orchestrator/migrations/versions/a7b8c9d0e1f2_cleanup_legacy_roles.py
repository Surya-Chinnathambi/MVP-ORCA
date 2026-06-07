"""cleanup_legacy_roles

Revision ID: a7b8c9d0e1f2
Revises: f5a6b7c8d9e0
Create Date: 2026-06-06 12:00:00.000000

Changes:
  - Delete legacy role rows (admin, reviewer, client) from roles table
  - These are replaced by the 10 canonical RBAC.md roles (platform_admin,
    senior_reviewer, client_approver, client_contributor already seeded in earlier stages)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_ROLES = ("admin", "reviewer", "client")


def upgrade() -> None:
    # Remove permissions tied to legacy roles first (FK constraint)
    conn = op.get_bind()
    for role_name in _LEGACY_ROLES:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :n"), {"n": role_name}
        ).fetchone()
        if row:
            conn.execute(
                sa.text("DELETE FROM permissions WHERE role_id = :rid"), {"rid": row[0]}
            )
            conn.execute(
                sa.text("DELETE FROM roles WHERE id = :rid"), {"rid": row[0]}
            )


def downgrade() -> None:
    pass  # Legacy roles are not restored — forward-only migration
