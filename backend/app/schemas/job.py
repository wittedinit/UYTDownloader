from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    entry_ids: list[uuid.UUID]
    format_mode: str = "video_audio"  # video_audio | audio_only | video_only
    quality: str = "best"  # best | 1080p | 720p | 480p | audio_only
    sponsorblock_action: str = "keep"  # keep | mark_chapters | remove
    embed_subtitles: bool = False
    normalize_audio: bool = False
    playback_speed: float = 1.0  # 0.25-4.0, 1.0 = normal
    output_format: str | None = None  # mp4_h264, mp4_h265, mkv_h264, webm_vp9, mp3, m4a_aac, opus, flac
    video_bitrate: str | None = None  # 8000k, 5000k, 3000k, 1500k, 800k
    output_dir: str | None = None


class JobStageOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    order: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class JobRequestOut(BaseModel):
    format_mode: str
    format_spec: str
    container: str
    max_height: int | None
    sponsorblock_action: str
    output_dir: str | None

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: uuid.UUID
    kind: str
    filename: str
    size_bytes: int | None
    duration: float | None
    mime_type: str | None
    download_url: str | None = None
    file_exists: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    priority: int
    progress_pct: float
    speed_bps: int | None
    eta_seconds: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    # Active stage info
    current_stage: str | None = None
    completed_stages: int = 0
    total_stages: int = 0

    # Entry summary
    entry_id: uuid.UUID | None
    entry_title: str | None = None
    entry_thumbnail: str | None = None

    model_config = {"from_attributes": True}


class JobDetail(JobOut):
    stages: list[JobStageOut] = []
    artifacts: list[ArtifactOut] = []
    request: JobRequestOut | None = None


class JobListResponse(BaseModel):
    jobs: list[JobOut]
    total: int
    page: int
    per_page: int


class JobCreateResponse(BaseModel):
    jobs: list[JobOut]
    total_requested: int = 0
    skipped_archive: int = 0
    skipped_not_found: int = 0
