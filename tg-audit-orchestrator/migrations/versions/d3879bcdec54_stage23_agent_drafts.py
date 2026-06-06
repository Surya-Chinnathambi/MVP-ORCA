"""stage23_agent_drafts

Revision ID: d3879bcdec54
Revises: ae0b9970b289
Create Date: 2026-06-05 11:11:15.980717

Changes:
- Create agent_drafts table (advisory AI agent output, status=draft until human accepts)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3879bcdec54'
down_revision: Union[str, None] = 'ae0b9970b289'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_drafts',
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('agent_type', sa.Enum(
            'classify_evidence', 'draft_finding', 'map_requirements',
            'qa_assist', 'draft_report_section', 'summarize_status',
            name='agent_type_enum',
        ), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'accepted', 'rejected', name='draft_status_enum'
        ), nullable=False),
        sa.Column('requested_by', sa.String(36), nullable=True),
        sa.Column('accepted_by', sa.String(36), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['accepted_by'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('agent_drafts')
