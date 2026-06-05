"""stage22_notifications

Revision ID: ae0b9970b289
Revises: 556d3346f04a
Create Date: 2026-06-05 11:06:32.793300

Changes:
- Create notifications table (web/email/telegram unified inbox)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'ae0b9970b289'
down_revision: Union[str, None] = '556d3346f04a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('channel', sa.Enum('web', 'email', 'telegram', name='notification_channel_enum'), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('notifications')
