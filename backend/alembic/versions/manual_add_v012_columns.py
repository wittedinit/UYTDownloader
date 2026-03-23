"""Add v0.1.2 columns and enum values.

Revision ID: manual_v012_cols
Revises: manual_v15_enums
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "manual_v012_cols"
down_revision = "manual_v15_enums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New enum values
    op.execute("ALTER TYPE stagetype ADD VALUE IF NOT EXISTS 'REENCODE'")
    op.execute("ALTER TYPE artifactkind ADD VALUE IF NOT EXISTS 'REENCODED'")

    # New columns on job_requests
    op.add_column("job_requests", sa.Column("output_format", sa.String(32), nullable=True))
    op.add_column("job_requests", sa.Column("video_bitrate", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("job_requests", "video_bitrate")
    op.drop_column("job_requests", "output_format")
