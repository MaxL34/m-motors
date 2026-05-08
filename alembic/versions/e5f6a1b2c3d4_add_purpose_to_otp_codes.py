"""add purpose to otp_codes

Revision ID: e5f6a1b2c3d4
Revises: 9de5eacb0397
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = '9de5eacb0397'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('otp_codes', sa.Column('purpose', sa.String(20), nullable=True))
    op.execute(
        "UPDATE otp_codes SET purpose = 'unlock' WHERE registration_json IS NULL AND purpose IS NULL"
    )
    op.execute(
        "UPDATE otp_codes SET purpose = 'registration' WHERE registration_json IS NOT NULL AND purpose IS NULL"
    )


def downgrade() -> None:
    op.drop_column('otp_codes', 'purpose')
