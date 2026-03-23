from __future__ import annotations

from pydantic import BaseModel


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
