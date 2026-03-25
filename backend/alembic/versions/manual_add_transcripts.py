"""Add transcripts table for full-text search.

Revision ID: manual_transcripts
Revises: ecbf26370492
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR

revision = "manual_transcripts"
down_revision = "ecbf26370492"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("video_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), server_default=""),
        sa.Column("channel", sa.String(256), server_default=""),
        sa.Column("language", sa.String(16), server_default="en"),
        sa.Column("content", sa.Text(), server_default=""),
        sa.Column("search_vector", TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_transcripts_entry_id", "transcripts", ["entry_id"])
    op.create_index("ix_transcripts_video_id", "transcripts", ["video_id"])
    op.create_index("ix_transcripts_search", "transcripts", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("transcripts")
