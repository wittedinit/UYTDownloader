"""Transcript model — stores subtitle text for full-text search across downloads."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Denormalized for fast display without joins
    video_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    channel: Mapped[str] = mapped_column(String(256), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    # Full transcript text (can be large)
    content: Mapped[str] = mapped_column(Text, default="")
    # PostgreSQL tsvector for full-text search — generated column
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_transcripts_search", "search_vector", postgresql_using="gin"),
    )
