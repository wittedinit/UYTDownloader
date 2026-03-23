"""Compilations API: merge multiple downloaded entries into one file."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artifact import Artifact
from app.models.entry import Entry
from app.models.enums import ArtifactKind, JobKind, JobStatus, StageStatus, StageType
from app.models.job import Job, JobStage
from app.schemas.compilation import CompilationRequest, CompilationResponse

router = APIRouter(prefix="/api/compilations", tags=["compilations"])


@router.post("", response_model=CompilationResponse, status_code=201)
async def create_compilation(req: CompilationRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a compilation job that merges multiple entries into one file.
    Entries must have already been downloaded (have artifacts).
    """
    if len(req.items) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 items for a compilation")

    # Verify all entries exist and have downloadable artifacts
    input_files = []
    for item in sorted(req.items, key=lambda x: x.position or 0):
        entry = await db.get(Entry, item.entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Entry {item.entry_id} not found")

        # Find best artifact for this entry (prefer cleaned > merged > audio > video)
        artifact = None
        for kind in [ArtifactKind.CLEANED, ArtifactKind.MERGED, ArtifactKind.AUDIO_STREAM, ArtifactKind.VIDEO_STREAM]:
            result = await db.execute(
                select(Artifact)
                .join(Job, Job.id == Artifact.job_id)
                .where(
                    Job.entry_id == entry.id,
                    Job.status == JobStatus.COMPLETED,
                    Artifact.kind == kind,
                )
                .order_by(Artifact.created_at.desc())
                .limit(1)
            )
            artifact = result.scalar_one_or_none()
            if artifact:
                break

        if not artifact:
            raise HTTPException(
                status_code=409,
                detail=f"Entry '{entry.title}' has no completed download. Download it first.",
            )

        input_files.append({
            "entry_id": str(entry.id),
            "path": artifact.path,
            "title": entry.title or entry.external_video_id,
            "duration": entry.duration,
        })

    # Create compilation job
    job = Job(kind=JobKind.COMPILE, status=JobStatus.PENDING)
    db.add(job)
    await db.flush()

    # Single COMPILE stage
    stage = JobStage(
        job_id=job.id,
        type=StageType.FINALIZE,  # Reuse finalize for now
        order=0,
    )
    db.add(stage)
    await db.flush()

    # Dispatch compilation task
    from app.worker.tasks import run_compilation

    try:
        from app.celery_app import celery
        task = run_compilation.delay(
            str(job.id),
            str(stage.id),
            input_files,
            req.mode,
            req.normalize_audio,
            req.title,
            req.output_dir,
        )
        job.status = JobStatus.QUEUED
        job.celery_task_id = task.id
    except Exception:
        try:
            from app.celery_app import celery
            celery.close()
            task = run_compilation.delay(
                str(job.id),
                str(stage.id),
                input_files,
                req.mode,
                req.normalize_audio,
                req.title,
                req.output_dir,
            )
            job.status = JobStatus.QUEUED
            job.celery_task_id = task.id
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Queue unavailable: {e}")

    await db.flush()

    return CompilationResponse(
        job_id=job.id,
        status=job.status.value,
        item_count=len(input_files),
    )
