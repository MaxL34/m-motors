"""add locked_at to users

Revision ID: 9de5eacb0397
Revises: c9d1e2f3a4b5
Create Date: 2026-04-30 09:13:11.132718

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9de5eacb0397'
down_revision: Union[str, Sequence[str], None] = 'c9d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'locked_at')
