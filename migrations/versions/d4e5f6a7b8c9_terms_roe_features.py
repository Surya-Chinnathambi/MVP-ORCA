"""terms_roe_features

Revision ID: d4e5f6a7b8c9
Revises: 4cdd16178f9d
Create Date: 2026-06-07 10:00:00.000000

Changes:
  1. users: add terms_accepted_at (DateTime, nullable)
  2. projects: add roe_data (JSON, nullable) for Rules of Engagement data
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = '4cdd16178f9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True)
        )

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('roe_data', sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('roe_data')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('terms_accepted_at')
