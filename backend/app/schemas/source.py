from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.entry import EntryOut


class SourceOut(BaseModel):
    id: uuid.UUID
    type: str
    canonical_url: str
    external_id: str
    title: str | None
    uploader: str | None
    thumbnail_url: str | None
    entry_count: int
    last_scanned_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceWithEntries(SourceOut):
    entries: list[EntryOut] = []


class SourceListResponse(BaseModel):
    sources: list[SourceOut]
    total: int
