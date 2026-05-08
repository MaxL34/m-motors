"""merge migration branches

Revision ID: 9608c40c3d33
Revises: a1b2c3d4e5f6, b1c2d3e4f5a6, e5f6a1b2c3d4
Create Date: 2026-05-08 11:16:56.532867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9608c40c3d33'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'b1c2d3e4f5a6', 'e5f6a1b2c3d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
