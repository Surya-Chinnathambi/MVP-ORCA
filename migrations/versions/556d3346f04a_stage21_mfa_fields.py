"""stage21_mfa_fields

Revision ID: 556d3346f04a
Revises: a76e67caa9e1
Create Date: 2026-06-05 11:02:10.930334

Changes:
- users: add mfa_secret (nullable), mfa_enabled (bool, default False),
         mfa_recovery_hashes (JSON, nullable)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '556d3346f04a'
down_revision: Union[str, None] = 'a76e67caa9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mfa_secret', sa.String(512), nullable=True))
        batch_op.add_column(sa.Column(
            'mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()
        ))
        batch_op.add_column(sa.Column('mfa_recovery_hashes', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('mfa_recovery_hashes')
        batch_op.drop_column('mfa_enabled')
        batch_op.drop_column('mfa_secret')
