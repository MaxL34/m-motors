"""add permanent delete history to client files

Revision ID: a7c32f1d8b04
Revises: f3a91d2b5e07
Create Date: 2026-05-05 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a7c32f1d8b04"
down_revision = "f3a91d2b5e07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_files", sa.Column("permanently_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("client_files", sa.Column("permanently_deleted_by_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("client_files", sa.Column("permanently_deleted_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("client_files", "permanently_deleted_reason")
    op.drop_column("client_files", "permanently_deleted_by_admin_id")
    op.drop_column("client_files", "permanently_deleted_at")
