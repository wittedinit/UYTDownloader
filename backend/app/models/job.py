import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    JobKind,
    JobStatus,
    SponsorBlockAction,
    StageStatus,
    StageType,
)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[JobKind]
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entries.id", ondelete="SET NULL")
    )
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)
    priority: Mapped[int] = mapped_column(default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(256))

    # Progress (denormalized for fast polling)
    progress_pct: Mapped[float] = mapped_column(default=0.0)
    speed_bps: Mapped[int | None]
    eta_seconds: Mapped[int | None]

    # Diagnostics
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)

    entry: Mapped["Entry | None"] = relationship(back_populates="jobs")  # noqa: F821
    request: Mapped["JobRequest | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    stages: Mapped[list["JobStage"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobStage.order"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="job", cascade="all, delete-orphan", passive_deletes=True)  # noqa: F821


class JobRequest(Base):
    """Immutable config snapshot frozen at job creation. Retries use this exact config."""

    __tablename__ = "job_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True
    )
    format_mode: Mapped[str] = mapped_column(String(32))  # video_audio | audio_only | video_only
    format_spec: Mapped[str] = mapped_column(String(256))  # resolved yt-dlp format string
    container: Mapped[str] = mapped_column(String(16), default="mp4")
    max_height: Mapped[int | None]
    sponsorblock_action: Mapped[SponsorBlockAction] = mapped_column(
        default=SponsorBlockAction.KEEP
    )
    output_dir: Mapped[str | None] = mapped_column(String(1024))
    cookie_file: Mapped[str | None] = mapped_column(String(1024))
    output_format: Mapped[str | None] = mapped_column(String(32))  # mp4_h264, mp3, etc.
    video_bitrate: Mapped[str | None] = mapped_column(String(16))  # 5000k, etc.
    playback_speed: Mapped[float] = mapped_column(default=1.0)
    output_signature_hash: Mapped[str] = mapped_column(String(64), index=True)

    job: Mapped["Job"] = relationship(back_populates="request")


class JobStage(TimestampMixin, Base):
    __tablename__ = "job_stages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[StageType]
    status: Mapped[StageStatus] = mapped_column(default=StageStatus.PENDING)
    order: Mapped[int]

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    log_file: Mapped[str | None] = mapped_column(String(1024))

    job: Mapped["Job"] = relationship(back_populates="stages")
