from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EntryOut(BaseModel):
    id: uuid.UUID
    external_video_id: str
    title: str
    duration: float | None
    upload_date: str | None
    thumbnail_url: str | None
    availability: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EntryDetail(EntryOut):
    metadata_json: dict[str, Any] | None = None
    format_snapshot: FormatSnapshotOut | None = None


class FormatSnapshotOut(BaseModel):
    id: uuid.UUID
    fetched_at: datetime
    expires_at: datetime
    formats_json: list[dict[str, Any]]
    subtitles_json: dict[str, Any] | None = None
    chapters_json: list[dict[str, Any]] | None = None

    model_config = {"from_attributes": True}


class EntryListResponse(BaseModel):
    entries: list[EntryOut]
    total: int
    page: int
    per_page: int
