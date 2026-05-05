"""add soft delete to client files

Revision ID: f3a91d2b5e07
Revises: cea24bc8b8c8
Create Date: 2026-05-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f3a91d2b5e07"
down_revision = "beaab374f5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_files", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("client_files", sa.Column("deleted_by_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("client_files", "deleted_by_admin_id")
    op.drop_column("client_files", "deleted_at")
