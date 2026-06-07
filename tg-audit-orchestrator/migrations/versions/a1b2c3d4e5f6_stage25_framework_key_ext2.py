"""stage25_framework_key_ext2

Revision ID: a1b2c3d4e5f6
Revises: f3a1b2c4d5e6
Create Date: 2026-06-05 13:00:00.000000

Changes:
- Extend framework_key_enum with isaca, tg_baseline
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STAGE24_KEYS = [
    "dpdp_act", "owasp_asvs", "owasp_wstg", "owasp_api10", "ptes",
    "iso_27001", "iso_27002", "iso_27701", "eu_gdpr", "nist",
]

_STAGE25_KEYS = _STAGE24_KEYS + ["isaca", "tg_baseline"]


def upgrade() -> None:
    with op.batch_alter_table("frameworks", schema=None) as batch_op:
        batch_op.alter_column(
            "key",
            existing_type=sa.Enum(*_STAGE24_KEYS, name="framework_key_enum"),
            type_=sa.Enum(*_STAGE25_KEYS, name="framework_key_enum"),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("frameworks", schema=None) as batch_op:
        batch_op.alter_column(
            "key",
            existing_type=sa.Enum(*_STAGE25_KEYS, name="framework_key_enum"),
            type_=sa.Enum(*_STAGE24_KEYS, name="framework_key_enum"),
            existing_nullable=False,
        )
