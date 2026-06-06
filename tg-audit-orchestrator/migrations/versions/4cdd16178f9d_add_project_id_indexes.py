"""add_project_id_indexes

Revision ID: 4cdd16178f9d
Revises: a7b8c9d0e1f2
Create Date: 2026-06-06 22:05:17.896279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cdd16178f9d'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'], unique=False)
    op.create_index('ix_findings_project_id', 'findings', ['project_id'], unique=False)
    op.create_index('ix_findings_severity', 'findings', ['severity'], unique=False)
    op.create_index('ix_evidence_requests_project_id', 'evidence_requests', ['project_id'], unique=False)
    op.create_index('ix_evidence_items_project_id', 'evidence_items', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_evidence_items_project_id', table_name='evidence_items')
    op.drop_index('ix_evidence_requests_project_id', table_name='evidence_requests')
    op.drop_index('ix_findings_severity', table_name='findings')
    op.drop_index('ix_findings_project_id', table_name='findings')
    op.drop_index('ix_tasks_project_id', table_name='tasks')
