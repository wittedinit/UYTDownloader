import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FormatSnapshot(Base):
    __tablename__ = "format_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    formats_json: Mapped[list] = mapped_column(JSON, default=list)
    subtitles_json: Mapped[dict | None] = mapped_column(JSON)
    chapters_json: Mapped[list | None] = mapped_column(JSON)

    entry: Mapped["Entry"] = relationship(back_populates="format_snapshots")  # noqa: F821
