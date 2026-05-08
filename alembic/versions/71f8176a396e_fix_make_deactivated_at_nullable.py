"""fix: make deactivated_at nullable

Revision ID: 71f8176a396e
Revises: b58cbd9393dc
Create Date: 2026-04-17 15:38:48.468746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71f8176a396e'
down_revision: Union[str, Sequence[str], None] = 'b58cbd9393dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('vehicles', 'deactivated_at', nullable=True)

def downgrade() -> None:
    op.alter_column('vehicles', 'deactivated_at', nullable=False)