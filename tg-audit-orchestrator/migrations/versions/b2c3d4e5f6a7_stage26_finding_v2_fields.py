"""stage26_finding_v2_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-05 14:00:00.000000

Changes:
- Add retest_status (String 50, nullable), phase_tag (String 50, nullable),
  ptorc_run_id (String 255, nullable), pack_scoped_data (JSON, nullable)
  to the findings table (via batch_alter_table for SQLite compatibility).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retest_status", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("phase_tag", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("ptorc_run_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("pack_scoped_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("findings", schema=None) as batch_op:
        batch_op.drop_column("pack_scoped_data")
        batch_op.drop_column("ptorc_run_id")
        batch_op.drop_column("phase_tag")
        batch_op.drop_column("retest_status")
