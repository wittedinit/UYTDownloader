"""Sources API: list and view probed sources and their entries."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entry import Entry
from app.models.format_snapshot import FormatSnapshot
from app.models.source import Source
from app.models.source_entry import SourceEntry
from app.schemas.entry import EntryDetail, EntryListResponse, EntryOut, FormatSnapshotOut
from app.schemas.source import SourceListResponse, SourceOut

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    type: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Source)
    count_stmt = select(func.count(Source.id))

    if type:
        stmt = stmt.where(Source.type == type)
        count_stmt = count_stmt.where(Source.type == type)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Source.title.ilike(pattern) | Source.uploader.ilike(pattern))
        count_stmt = count_stmt.where(
            Source.title.ilike(pattern) | Source.uploader.ilike(pattern)
        )

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(Source.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    return SourceListResponse(
        sources=[SourceOut.model_validate(s) for s in sources],
        total=total,
    )


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceOut.model_validate(source)


@router.get("/sources/{source_id}/entries", response_model=EntryListResponse)
async def get_source_entries(
    source_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Count
    count_stmt = (
        select(func.count(SourceEntry.id))
        .where(SourceEntry.source_id == source_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated entries
    stmt = (
        select(Entry)
        .join(SourceEntry, SourceEntry.entry_id == Entry.id)
        .where(SourceEntry.source_id == source_id)
        .order_by(SourceEntry.position.nulls_last(), Entry.title)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return EntryListResponse(
        entries=[EntryOut.model_validate(e) for e in entries],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/entries/{entry_id}", response_model=EntryDetail)
async def get_entry_detail(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Get latest format snapshot
    snap_stmt = (
        select(FormatSnapshot)
        .where(FormatSnapshot.entry_id == entry.id)
        .order_by(FormatSnapshot.fetched_at.desc())
        .limit(1)
    )
    snap = (await db.execute(snap_stmt)).scalar_one_or_none()

    detail = EntryDetail.model_validate(entry)
    if snap:
        detail.format_snapshot = FormatSnapshotOut.model_validate(snap)
    return detail
