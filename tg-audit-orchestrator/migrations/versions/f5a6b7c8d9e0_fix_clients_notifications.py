"""fix_clients_notifications

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-06 11:00:00.000000

Changes:
  1. clients: rename name → entity_name
  2. notifications: rename user_id→recipient_user_id, event_type→kind;
     add organization_id, scheduled_for, sent_at;
     add status column (backfill from is_read), drop is_read
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. clients: rename name → entity_name
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.alter_column('name', new_column_name='entity_name')

    # 2. notifications: align to db.md schema
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.alter_column('user_id', new_column_name='recipient_user_id')
        batch_op.alter_column('event_type', new_column_name='kind')
        batch_op.add_column(sa.Column('organization_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))
        # Add status column (replaces is_read boolean)
        batch_op.add_column(
            sa.Column('status', sa.String(20), nullable=False, server_default='pending')
        )

    # Backfill status from is_read
    op.execute(
        "UPDATE notifications SET status = 'read' WHERE is_read = 1"
    )
    op.execute(
        "UPDATE notifications SET status = 'sent' WHERE is_read = 0"
    )

    # Drop is_read now that status is populated
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_column('is_read')
        batch_op.create_foreign_key(
            'fk_notif_organization_id', 'organizations', ['organization_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notif_organization_id', type_='foreignkey')
        batch_op.add_column(sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.drop_column('status')
        batch_op.drop_column('sent_at')
        batch_op.drop_column('scheduled_for')
        batch_op.drop_column('organization_id')
        batch_op.alter_column('kind', new_column_name='event_type')
        batch_op.alter_column('recipient_user_id', new_column_name='user_id')

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.alter_column('entity_name', new_column_name='name')
