"""Add V1.5b enum values for metadata embedding.

Revision ID: manual_v15b_enums
Revises: manual_v15_enums
Create Date: 2026-03-24
"""
from alembic import op

# revision identifiers
revision = "manual_v15b_enums"
down_revision = "manual_v15_enums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE artifactkind ADD VALUE IF NOT EXISTS 'TAGGED'")
    op.execute("ALTER TYPE stagetype ADD VALUE IF NOT EXISTS 'EMBED_METADATA'")


def downgrade() -> None:
    pass
