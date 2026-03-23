from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ProbeRequest(BaseModel):
    url: str


class ProbeResponse(BaseModel):
    probe_id: str  # Celery task ID
    status: str  # "probing" | "completed" | "failed"


class ProbeResult(BaseModel):
    status: str
    source_id: str | None = None
    entry_count: int = 0
    error: str | None = None
