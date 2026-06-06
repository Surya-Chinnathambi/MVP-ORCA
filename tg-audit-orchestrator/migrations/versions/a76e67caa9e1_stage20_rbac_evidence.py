"""stage20_rbac_evidence

Revision ID: a76e67caa9e1
Revises: d564468c133e
Create Date: 2026-06-05 10:57:06.513530

Changes:
- evidence_items: add is_restricted boolean (default False)
- permissions.scope_level: extend enum to include organization, evidence_item, deliverable
- roles.name: extend enum to include 5 new Phase 2 roles
- Seed the 5 new role rows into the roles table
"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = 'a76e67caa9e1'
down_revision: Union[str, None] = 'd564468c133e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_ROLES = [
    "platform_admin",
    "lead_consultant",
    "senior_reviewer",
    "client_approver",
    "client_contributor",
]

_NEW_SCOPE_LEVEL_ENUM = sa.Enum(
    'client', 'project', 'organization', 'evidence_item', 'deliverable',
    name='scope_level_enum',
)

_NEW_ROLE_ENUM = sa.Enum(
    'admin', 'partner', 'pm', 'analyst', 'reviewer', 'qa', 'client', 'readonly',
    'platform_admin', 'lead_consultant', 'senior_reviewer', 'client_approver', 'client_contributor',
    name='role_name_enum',
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upgrade() -> None:
    # Add is_restricted to evidence_items
    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'is_restricted', sa.Boolean(), nullable=False, server_default=sa.false()
        ))

    # Extend scope_level enum on permissions table (SQLite: VARCHAR, no enforcement)
    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.alter_column(
            'scope_level',
            existing_type=sa.VARCHAR(length=7),
            type_=_NEW_SCOPE_LEVEL_ENUM,
            existing_nullable=False,
        )

    # Extend role_name enum on roles table
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column(
            'name',
            existing_type=sa.VARCHAR(length=8),
            type_=_NEW_ROLE_ENUM,
            existing_nullable=False,
        )

    # Seed new role rows (skip any that already exist)
    now = _now()
    conn = op.get_bind()
    roles_table = sa.table('roles',
        sa.column('id', sa.String),
        sa.column('name', sa.String),
        sa.column('created_at', sa.String),
        sa.column('updated_at', sa.String),
    )
    existing_names = {row[0] for row in conn.execute(sa.select(sa.text('name')).select_from(sa.text('roles')))}
    to_insert = [
        {"id": str(uuid.uuid4()), "name": r, "created_at": now, "updated_at": now}
        for r in _NEW_ROLES
        if r not in existing_names
    ]
    if to_insert:
        op.bulk_insert(roles_table, to_insert)


def downgrade() -> None:
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column(
            'name',
            existing_type=_NEW_ROLE_ENUM,
            type_=sa.VARCHAR(length=8),
            existing_nullable=False,
        )
    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.alter_column(
            'scope_level',
            existing_type=_NEW_SCOPE_LEVEL_ENUM,
            type_=sa.VARCHAR(length=7),
            existing_nullable=False,
        )
    with op.batch_alter_table('evidence_items', schema=None) as batch_op:
        batch_op.drop_column('is_restricted')
