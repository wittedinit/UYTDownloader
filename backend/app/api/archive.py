"""Archive API — browse and manage the deduplication archive."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.archive import ArchiveRecord
from app.models.entry import Entry

router = APIRouter(prefix="/api/archive", tags=["archive"])


class ArchiveItem(PydanticBaseModel):
    id: uuid.UUID
    external_video_id: str
    canonical_url: str
    output_signature_hash: str
    artifact_id: uuid.UUID | None = None
    first_downloaded_at: str
    # Joined from entries table
    title: str | None = None
    thumbnail_url: str | None = None
    uploader: str | None = None


class ArchiveListResponse(PydanticBaseModel):
    records: list[ArchiveItem]
    total: int
    page: int
    per_page: int


@router.get("", response_model=ArchiveListResponse)
async def list_archive(
    page: int = 1,
    per_page: int = 50,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all archive records with optional search."""
    query = (
        select(ArchiveRecord, Entry)
        .outerjoin(Entry, Entry.external_video_id == ArchiveRecord.external_video_id)
        .order_by(ArchiveRecord.first_downloaded_at.desc())
    )
    count_query = select(func.count()).select_from(ArchiveRecord)

    if search:
        # Search by video title or video ID
        pattern = f"%{search}%"
        query = query.where(
            (Entry.title.ilike(pattern)) | (ArchiveRecord.external_video_id.ilike(pattern))
        )
        count_query = (
            select(func.count())
            .select_from(ArchiveRecord)
            .outerjoin(Entry, Entry.external_video_id == ArchiveRecord.external_video_id)
            .where(
                (Entry.title.ilike(pattern)) | (ArchiveRecord.external_video_id.ilike(pattern))
            )
        )

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    rows = (await db.execute(query.offset(offset).limit(per_page))).all()

    records = []
    for archive_rec, entry in rows:
        records.append(ArchiveItem(
            id=archive_rec.id,
            external_video_id=archive_rec.external_video_id,
            canonical_url=archive_rec.canonical_url,
            output_signature_hash=archive_rec.output_signature_hash,
            artifact_id=archive_rec.artifact_id,
            first_downloaded_at=archive_rec.first_downloaded_at.isoformat(),
            title=entry.title if entry else None,
            thumbnail_url=entry.thumbnail_url if entry else None,
            uploader=getattr(entry, "uploader", None) if entry else None,
        ))

    return ArchiveListResponse(records=records, total=total, page=page, per_page=per_page)


@router.delete("/{record_id}", status_code=204)
async def delete_archive_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an archive record (allows re-downloading that video)."""
    rec = await db.get(ArchiveRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Archive record not found")
    await db.delete(rec)
    await db.flush()


class BulkDeleteArchiveRequest(PydanticBaseModel):
    record_ids: list[uuid.UUID]


@router.post("/bulk-delete", status_code=200)
async def bulk_delete_archive(
    body: BulkDeleteArchiveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple archive records."""
    deleted = 0
    for rid in body.record_ids:
        rec = await db.get(ArchiveRecord, rid)
        if rec:
            await db.delete(rec)
            deleted += 1
    await db.flush()
    return {"deleted": deleted, "total": len(body.record_ids)}
