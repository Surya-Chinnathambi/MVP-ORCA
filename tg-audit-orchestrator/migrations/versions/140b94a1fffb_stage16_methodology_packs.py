"""stage16_methodology_packs

Revision ID: 140b94a1fffb
Revises: a6513e362bf9
Create Date: 2026-06-05 10:08:20.188612

Changes:
- Create methodology_packs table (versioned, lifecycle-governed pack objects)
- Make ApprovalRequest.project_id nullable (pack-level approvals have no project)
- Nullify existing projects.pack_id values (old string keys are not UUIDs)
- Change projects.pack_id from VARCHAR(100) → VARCHAR(36) FK → methodology_packs
- Add organization_id FK to clients (already present in model since Stage 14;
  Alembic now detects it due to schema registration order)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '140b94a1fffb'
down_revision: Union[str, None] = 'a6513e362bf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'methodology_packs',
        sa.Column('organization_id', sa.String(36), nullable=True),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('lifecycle', sa.Enum(
            'draft', 'internal_review', 'approved', 'active', 'deprecated', 'archived',
            name='pack_lifecycle_enum',
        ), nullable=False),
        sa.Column('source_json', sa.JSON(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_methodology_packs_key', 'methodology_packs', ['key'], unique=False)

    # Make ApprovalRequest.project_id nullable for platform-level approvals
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.alter_column('project_id', existing_type=sa.String(36), nullable=True)

    # Nullify old string pack_id values before changing column type + adding FK
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE projects SET pack_id = NULL WHERE pack_id IS NOT NULL"))

    # Change projects.pack_id: String(100) → String(36) + FK to methodology_packs
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.alter_column(
            'pack_id',
            existing_type=sa.String(100),
            type_=sa.String(36),
            existing_nullable=True,
        )
        batch_op.create_foreign_key(
            'fk_projects_pack_id_methodology_packs',
            'methodology_packs', ['pack_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('fk_projects_pack_id_methodology_packs', type_='foreignkey')
        batch_op.alter_column(
            'pack_id',
            existing_type=sa.String(36),
            type_=sa.String(100),
            existing_nullable=True,
        )

    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.alter_column('project_id', existing_type=sa.String(36), nullable=False)

    op.drop_index('ix_methodology_packs_key', table_name='methodology_packs')
    op.drop_table('methodology_packs')
