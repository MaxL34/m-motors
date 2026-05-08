"""add login attempts to users

Revision ID: c9d1e2f3a4b5
Revises: f3a7c92e81b4
Create Date: 2026-04-29 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'f3a7c92e81b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_at")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "is_locked")
