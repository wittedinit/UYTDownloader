"""Probe API: submit URL for metadata extraction, poll results."""

from __future__ import annotations

import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.entry import Entry
from app.models.format_snapshot import FormatSnapshot
from app.models.source import Source
from app.models.source_entry import SourceEntry
from app.schemas.entry import EntryOut, FormatSnapshotOut
from app.schemas.probe import ProbeRequest, ProbeResponse, ProbeResult
from app.schemas.source import SourceOut
from app.worker.tasks import run_probe

router = APIRouter(prefix="/api", tags=["probe"])


@router.post("/probe", response_model=ProbeResponse, status_code=202)
async def submit_probe(req: ProbeRequest):
    """Submit a URL for metadata extraction. Returns a probe_id to poll."""
    from app.celery_app import celery

    try:
        task = run_probe.delay(req.url)
    except Exception:
        # Connection may be stale — close pool and retry once
        try:
            celery.close()
            task = run_probe.delay(req.url)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Queue unavailable: {e}")
    return ProbeResponse(probe_id=task.id, status="probing")


@router.get("/probe/{probe_id}")
async def get_probe_result(probe_id: str, db: AsyncSession = Depends(get_db)):
    """Poll probe status. When completed, returns source + entries + format snapshot."""
    result = AsyncResult(probe_id)

    if result.state == "PENDING":
        return {"status": "probing", "probe_id": probe_id}
    elif result.state == "STARTED":
        return {"status": "probing", "probe_id": probe_id}
    elif result.state == "FAILURE":
        return {
            "status": "failed",
            "probe_id": probe_id,
            "error": str(result.result),
        }
    elif result.state == "SUCCESS":
        task_result = result.result
        if not task_result or task_result.get("status") == "failed":
            return {
                "status": "failed",
                "probe_id": probe_id,
                "error": task_result.get("error", "Unknown error") if task_result else "No result",
            }

        source_id = task_result.get("source_id")
        if not source_id:
            return {"status": "failed", "probe_id": probe_id, "error": "No source created"}

        # Fetch source with entries
        source = await db.get(Source, uuid.UUID(source_id))
        if not source:
            return {"status": "failed", "probe_id": probe_id, "error": "Source not found"}

        # Get entries via join table, ordered by position
        stmt = (
            select(Entry)
            .join(SourceEntry, SourceEntry.entry_id == Entry.id)
            .where(SourceEntry.source_id == source.id)
            .order_by(SourceEntry.position.nulls_last(), Entry.title)
        )
        entries_result = await db.execute(stmt)
        entries = entries_result.scalars().all()

        # For single video, include format snapshot
        format_snapshot = None
        if len(entries) == 1:
            snap_stmt = (
                select(FormatSnapshot)
                .where(FormatSnapshot.entry_id == entries[0].id)
                .order_by(FormatSnapshot.fetched_at.desc())
                .limit(1)
            )
            snap_result = await db.execute(snap_stmt)
            snap = snap_result.scalar_one_or_none()
            if snap:
                format_snapshot = FormatSnapshotOut.model_validate(snap)

        return {
            "status": "completed",
            "probe_id": probe_id,
            "source": SourceOut.model_validate(source),
            "entries": [EntryOut.model_validate(e) for e in entries],
            "entry_count": len(entries),
            "format_snapshot": format_snapshot,
        }

    return {"status": result.state.lower(), "probe_id": probe_id}
