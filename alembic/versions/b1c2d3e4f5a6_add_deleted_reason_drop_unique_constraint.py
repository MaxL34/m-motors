"""add deleted_reason and drop unique_user_vehicle_file constraint

Revision ID: b1c2d3e4f5a6
Revises: a7c32f1d8b04
Create Date: 2026-05-05 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a7c32f1d8b04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_files", sa.Column("deleted_reason", sa.Text(), nullable=True))
    op.drop_constraint("unique_user_vehicle_file", "client_files", type_="unique")


def downgrade() -> None:
    op.drop_column("client_files", "deleted_reason")
    op.create_unique_constraint("unique_user_vehicle_file", "client_files", ["user_id", "vehicle_id"])
