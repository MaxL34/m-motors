"""add vehicle_status_history table

Revision ID: cea24bc8b8c8
Revises: 71f8176a396e
Create Date: 2026-04-20 15:33:00.123968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cea24bc8b8c8'
down_revision: Union[str, Sequence[str], None] = '71f8176a396e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicle_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum("ACTIVATED", "DEACTIVATED", name="statusaction"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vehicle_status_history_vehicle_id",
        "vehicle_status_history",
        ["vehicle_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_status_history_vehicle_id", table_name="vehicle_status_history")
    op.drop_table("vehicle_status_history")
    op.execute("DROP TYPE IF EXISTS statusaction")
