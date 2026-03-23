from __future__ import annotations

import uuid

from pydantic import BaseModel


class CompilationItem(BaseModel):
    entry_id: uuid.UUID
    position: int | None = None  # Override ordering


class CompilationRequest(BaseModel):
    """Request to build a compilation from multiple entries."""
    items: list[CompilationItem]
    mode: str = "video_chapters"  # video_chapters | video_no_chapters | audio_chapters | audio_no_chapters
    quality: str = "best"
    normalize_audio: bool = False
    title: str | None = None  # Output filename
    output_dir: str | None = None


class CompilationResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    item_count: int
