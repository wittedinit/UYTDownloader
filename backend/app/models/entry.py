import uuid

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EntryAvailability


class Entry(TimestampMixin, Base):
    __tablename__ = "entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_video_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    duration: Mapped[float | None]
    upload_date: Mapped[str | None] = mapped_column(String(10))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    availability: Mapped[EntryAvailability] = mapped_column(
        default=EntryAvailability.UNKNOWN
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    source_entries: Mapped[list["SourceEntry"]] = relationship(  # noqa: F821
        back_populates="entry"
    )
    format_snapshots: Mapped[list["FormatSnapshot"]] = relationship(  # noqa: F821
        back_populates="entry", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="entry")  # noqa: F821
