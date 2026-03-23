import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SourceEntry(Base):
    __tablename__ = "source_entries"
    __table_args__ = (UniqueConstraint("source_id", "entry_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int | None]  # playlist ordering
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped["Source"] = relationship(back_populates="source_entries")  # noqa: F821
    entry: Mapped["Entry"] = relationship(back_populates="source_entries")  # noqa: F821
