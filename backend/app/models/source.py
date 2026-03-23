import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SourceType


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[SourceType]
    canonical_url: Mapped[str] = mapped_column(String(2048), unique=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    uploader: Mapped[str | None] = mapped_column(String(256))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    entry_count: Mapped[int] = mapped_column(default=0)
    last_scanned_at: Mapped[datetime | None]

    source_entries: Mapped[list["SourceEntry"]] = relationship(  # noqa: F821
        back_populates="source", cascade="all, delete-orphan"
    )
