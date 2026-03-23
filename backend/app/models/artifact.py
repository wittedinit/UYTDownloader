import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ArtifactKind


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ArtifactKind]
    path: Mapped[str] = mapped_column(String(2048))
    filename: Mapped[str] = mapped_column(String(512))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    duration: Mapped[float | None]
    size_bytes: Mapped[int | None]
    mime_type: Mapped[str | None] = mapped_column(String(128))

    # Lineage
    produced_by_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_stages.id", ondelete="SET NULL")
    )
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="artifacts")  # noqa: F821
