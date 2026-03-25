"""Search API: full-text search across transcripts and library."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.db import get_sync_session
from app.services.transcript_service import search_transcripts

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query("", description="Search query"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Full-text search across indexed transcripts. Returns ranked results with snippets."""
    if not q.strip():
        return {"results": [], "total": 0, "query": q}

    session = get_sync_session()
    try:
        return search_transcripts(session, q, limit=limit, offset=offset)
    finally:
        session.close()


@router.get("/stats")
async def search_stats():
    """Return transcript index statistics."""
    session = get_sync_session()
    try:
        result = session.execute(text("SELECT count(*), coalesce(sum(length(content)), 0) FROM transcripts"))
        row = result.one()
        return {
            "indexed_videos": row[0],
            "total_characters": row[1],
            "estimated_hours": round(row[1] / 15000, 1),  # ~15k chars per hour of speech
        }
    finally:
        session.close()
