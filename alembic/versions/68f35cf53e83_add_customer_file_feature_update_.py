"""add customer file feature: update document, add favorite, add IN_PROGRESS status

Revision ID: 68f35cf53e83
Revises: bdc42e45ab8a
Create Date: 2026-04-24 11:01:20.087017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '68f35cf53e83'
down_revision: Union[str, Sequence[str], None] = 'bdc42e45ab8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_DOCUMENT_TYPES = ('INVOICE', 'CONTRACT', 'INSURANCE', 'REGISTRATION', 'IDENTITY_PROOF', 'ADDRESS_PROOF', 'INSPECTION', 'OTHER')
NEW_DOCUMENT_TYPES = ('CNI', 'DRIVING_LICENSE', 'PROOF_OF_ADDRESS', 'PAY_SLIP_1', 'PAY_SLIP_2', 'PAY_SLIP_3', 'TAX_NOTICE', 'RIB')


def upgrade() -> None:
    # ── documenttype enum: remplacer les anciennes valeurs ────────────────────
    # Conversion temporaire en varchar pour pouvoir recréer l'enum
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE VARCHAR USING document_type::VARCHAR")
    op.execute("DROP TYPE documenttype")
    op.execute(f"CREATE TYPE documenttype AS ENUM {NEW_DOCUMENT_TYPES}")
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE documenttype USING document_type::documenttype")

    # ── clientfilestatus enum: ajouter IN_PROGRESS ────────────────────────────
    op.execute("ALTER TYPE clientfilestatus ADD VALUE IF NOT EXISTS 'IN_PROGRESS'")

    # ── nouvelles colonnes documents ──────────────────────────────────────────
    op.add_column('documents', sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'VALIDATED', 'REFUSED', name='documentstatus'), nullable=False, server_default='PENDING'))
    op.add_column('documents', sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('documents', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.drop_column('documents', 'expiration_date')


def downgrade() -> None:
    # ── restaurer les colonnes documents ─────────────────────────────────────
    op.add_column('documents', sa.Column('expiration_date', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    op.drop_column('documents', 'rejection_reason')
    op.drop_column('documents', 'is_locked')
    op.drop_column('documents', 'status')
    op.execute("DROP TYPE IF EXISTS documentstatus")

    # ── restaurer documenttype ────────────────────────────────────────────────
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE VARCHAR USING document_type::VARCHAR")
    op.execute("DROP TYPE documenttype")
    op.execute(f"CREATE TYPE documenttype AS ENUM {OLD_DOCUMENT_TYPES}")
    op.execute("ALTER TABLE documents ALTER COLUMN document_type TYPE documenttype USING document_type::documenttype")

    # Note: PostgreSQL ne supporte pas la suppression de valeurs d'enum,
    # IN_PROGRESS dans clientfilestatus ne peut pas être retiré sans recréer l'enum.
