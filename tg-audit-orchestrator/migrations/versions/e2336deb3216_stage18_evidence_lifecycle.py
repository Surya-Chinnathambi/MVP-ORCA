"""stage18_evidence_lifecycle

Revision ID: e2336deb3216
Revises: 140b94a1fffb
Create Date: 2026-06-05 10:46:53.220694

Changes:
- Create evidence_lifecycle_events table (append-only internal lifecycle log)
- Add evidence_items.internal_lifecycle_state (default 'intake')
- Add evidence_items.supersedes_id (nullable self-FK for supersede chain)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e2336deb3216'
down_revision: Union[str, None] = '140b94a1fffb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evidence_lifecycle_events',
        sa.Column('evidence_item_id', sa.String(36), nullable=False),
        sa.Column('from_state', sa.String(50), nullable=False),
        sa.Column('to_state', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.String(36), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['evidence_item_id'], ['evidence_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add new columns + self-FK to evidence_items via batch for SQLite compat
    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'internal_lifecycle_state',
            sa.String(50),
            nullable=False,
            server_default='intake',
        ))
        batch_op.add_column(sa.Column('supersedes_id', sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            'fk_evidence_items_supersedes_id',
            'evidence_items', ['supersedes_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_evidence_items_supersedes_id', type_='foreignkey')
        batch_op.drop_column('supersedes_id')
        batch_op.drop_column('internal_lifecycle_state')
    op.drop_table('evidence_lifecycle_events')
