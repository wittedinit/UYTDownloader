"""Add V1.5 enum values for artifact kinds and stage types.

Revision ID: manual_v15_enums
Revises: 841e1f6e41bf
Create Date: 2026-03-23
"""
from alembic import op

# revision identifiers
revision = "manual_v15_enums"
down_revision = "841e1f6e41bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new artifact kinds
    op.execute("ALTER TYPE artifactkind ADD VALUE IF NOT EXISTS 'NORMALIZED'")
    op.execute("ALTER TYPE artifactkind ADD VALUE IF NOT EXISTS 'SUBTITLED'")
    # Add new stage types
    op.execute("ALTER TYPE stagetype ADD VALUE IF NOT EXISTS 'EMBED_SUBTITLES'")
    op.execute("ALTER TYPE stagetype ADD VALUE IF NOT EXISTS 'NORMALIZE_AUDIO'")


def downgrade() -> None:
    # Postgres doesn't support removing enum values easily
    pass
