import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ArchiveRecord(Base):
    __tablename__ = "archive_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_video_id: Mapped[str] = mapped_column(String(64), index=True)
    canonical_url: Mapped[str] = mapped_column(String(2048))
    output_signature_hash: Mapped[str] = mapped_column(String(64), index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL")
    )
    first_downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
