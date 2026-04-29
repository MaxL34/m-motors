"""add otp_codes table

Revision ID: f3a7c92e81b4
Revises: beaab374f5a4
Create Date: 2026-04-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c92e81b4'
down_revision: Union[str, Sequence[str], None] = 'bdc42e45ab8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("registration_json", sa.Text(), nullable=True),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("pending_token", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pending_token", name="uq_otp_codes_pending_token"),
    )
    op.create_index("ix_otp_codes_id", "otp_codes", ["id"])
    op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])
    op.create_index("ix_otp_codes_pending_token", "otp_codes", ["pending_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_otp_codes_pending_token", table_name="otp_codes")
    op.drop_index("ix_otp_codes_user_id", table_name="otp_codes")
    op.drop_index("ix_otp_codes_id", table_name="otp_codes")
    op.drop_table("otp_codes")
