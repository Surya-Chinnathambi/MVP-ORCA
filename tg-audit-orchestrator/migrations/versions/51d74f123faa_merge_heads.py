"""merge_heads

Revision ID: 51d74f123faa
Revises: b0c1d2e3f4a5, 4cdd16178f9d
Create Date: 2026-06-06 22:39:05.747192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51d74f123faa'
down_revision: Union[str, None] = ('b0c1d2e3f4a5', '4cdd16178f9d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
