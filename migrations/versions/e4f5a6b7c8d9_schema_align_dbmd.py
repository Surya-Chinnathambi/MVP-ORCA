"""schema_align_dbmd

Revision ID: e4f5a6b7c8d9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-06 10:00:00.000000

Changes (align all tables to db.md as source of truth):
  1. work_modes: rename name→key, display_name→title
  2. users: rename mfa_recovery_hashes→recovery_codes
  3. users: add last_client_id, last_project_id, last_work_mode (Stage 19 context fields per db.md)
  4. evidence_items: rename item_metadata→metadata
  5. evidence_lifecycle_events: add supersedes_id (FK→evidence_items)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. work_modes: rename name→key, display_name→title
    with op.batch_alter_table('work_modes', schema=None) as batch_op:
        batch_op.alter_column('name', new_column_name='key')
        batch_op.alter_column('display_name', new_column_name='title')

    # 2. users: rename mfa_recovery_hashes→recovery_codes
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('mfa_recovery_hashes', new_column_name='recovery_codes')
        # 3. add Stage 19 context-restore fields per db.md
        batch_op.add_column(sa.Column('last_client_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('last_project_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('last_work_mode', sa.String(50), nullable=True))

    # Add FK constraints for the new user context fields (SQLite ignores FKs anyway but keeps schema clean)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_users_last_client_id', 'clients', ['last_client_id'], ['id'])
        batch_op.create_foreign_key('fk_users_last_project_id', 'projects', ['last_project_id'], ['id'])

    # 4. evidence_items: rename item_metadata→metadata
    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.alter_column('item_metadata', new_column_name='metadata')

    # 5. evidence_lifecycle_events: add supersedes_id
    with op.batch_alter_table('evidence_lifecycle_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('supersedes_id', sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            'fk_ele_supersedes_id', 'evidence_items', ['supersedes_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('evidence_lifecycle_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_ele_supersedes_id', type_='foreignkey')
        batch_op.drop_column('supersedes_id')

    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.alter_column('metadata', new_column_name='item_metadata')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_last_project_id', type_='foreignkey')
        batch_op.drop_constraint('fk_users_last_client_id', type_='foreignkey')
        batch_op.drop_column('last_work_mode')
        batch_op.drop_column('last_project_id')
        batch_op.drop_column('last_client_id')
        batch_op.alter_column('recovery_codes', new_column_name='mfa_recovery_hashes')

    with op.batch_alter_table('work_modes', schema=None) as batch_op:
        batch_op.alter_column('title', new_column_name='display_name')
        batch_op.alter_column('key', new_column_name='name')
