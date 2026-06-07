"""stage24_framework_key_ext

Revision ID: f3a1b2c4d5e6
Revises: d3879bcdec54
Create Date: 2026-06-05 12:00:00.000000

Changes:
- Extend framework_key_enum with iso_27001, iso_27002, iso_27701, eu_gdpr, nist
- Uses batch_alter_table for SQLite compatibility
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a1b2c4d5e6'
down_revision: Union[str, None] = 'd3879bcdec54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_KEYS = [
    "dpdp_act", "owasp_asvs", "owasp_wstg", "owasp_api10", "ptes",
    "iso_27001", "iso_27002", "iso_27701", "eu_gdpr", "nist",
]


def upgrade() -> None:
    with op.batch_alter_table("frameworks", schema=None) as batch_op:
        batch_op.alter_column(
            "key",
            existing_type=sa.Enum(
                "dpdp_act", "owasp_asvs", "owasp_wstg", "owasp_api10", "ptes",
                name="framework_key_enum",
            ),
            type_=sa.Enum(*_NEW_KEYS, name="framework_key_enum"),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("frameworks", schema=None) as batch_op:
        batch_op.alter_column(
            "key",
            existing_type=sa.Enum(*_NEW_KEYS, name="framework_key_enum"),
            type_=sa.Enum(
                "dpdp_act", "owasp_asvs", "owasp_wstg", "owasp_api10", "ptes",
                name="framework_key_enum",
            ),
            existing_nullable=False,
        )
