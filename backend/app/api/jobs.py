"""Jobs API: create, list, get, cancel download jobs."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.enums import JobStatus, StageStatus
from app.models.job import Job, JobStage
from app.schemas.job import (
    ArtifactOut,
    JobCreateRequest,
    JobCreateResponse,
    JobDetail,
    JobListResponse,
    JobOut,
    JobRequestOut,
    JobStageOut,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=201)
async def create_jobs(req: JobCreateRequest):
    """Create download jobs for selected entries and enqueue them."""
    from app.services.job_service import create_jobs as svc_create
    from app.worker.tasks import run_stage

    # Create jobs synchronously (service uses sync session)
    created = svc_create(
        entry_ids=req.entry_ids,
        format_mode=req.format_mode,
        quality=req.quality,
        sponsorblock_action=req.sponsorblock_action,
        output_dir=req.output_dir,
        embed_subtitles=req.embed_subtitles,
        normalize_audio=req.normalize_audio,
        output_format=req.output_format,
        video_bitrate=req.video_bitrate,
    )

    if not created:
        raise HTTPException(
            status_code=409,
            detail="No new jobs created — entries may already be archived with the same settings",
        )

    # Dispatch first stage of each job
    from app.services.job_service import _get_sync_session
    from app.models.job import JobStage as JobStageModel

    session = _get_sync_session()
    try:
        for job_data in created:
            job_id = job_data["id"]
            first_stage = session.execute(
                select(JobStageModel)
                .where(
                    JobStageModel.job_id == uuid.UUID(job_id),
                    JobStageModel.status == StageStatus.PENDING,
                )
                .order_by(JobStageModel.order)
                .limit(1)
            ).scalar_one_or_none()

            if first_stage:
                celery_result = run_stage.delay(job_id, str(first_stage.id))
                # Update job with celery task id
                from app.models.job import Job as JobModel
                job = session.get(JobModel, uuid.UUID(job_id))
                if job:
                    job.status = JobStatus.QUEUED
                    job.celery_task_id = celery_result.id
                    job_data["status"] = "queued"
        session.commit()
    finally:
        session.close()

    # Build response
    jobs_out = []
    for j in created:
        jobs_out.append(JobOut(
            id=uuid.UUID(j["id"]),
            kind=j["kind"],
            status=j["status"],
            priority=j["priority"],
            progress_pct=j["progress_pct"],
            speed_bps=j["speed_bps"],
            eta_seconds=j["eta_seconds"],
            error_code=j["error_code"],
            error_message=j["error_message"],
            entry_id=uuid.UUID(j["entry_id"]) if j.get("entry_id") else None,
            entry_title=j.get("entry_title"),
            entry_thumbnail=j.get("entry_thumbnail"),
            created_at=j["created_at"],
            updated_at=j["updated_at"],
        ))

    return JobCreateResponse(jobs=jobs_out)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List jobs with optional status filter."""
    query = select(Job).options(selectinload(Job.entry))

    if status:
        query = query.where(Job.status == JobStatus(status))

    # Count
    count_q = select(func.count()).select_from(Job)
    if status:
        count_q = count_q.where(Job.status == JobStatus(status))
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.order_by(Job.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[_job_to_out(j) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full job details including stages and artifacts."""
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.entry),
            selectinload(Job.stages),
            selectinload(Job.artifacts),
            selectinload(Job.request),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    out = _job_to_out(job)
    return JobDetail(
        **out.model_dump(),
        stages=[
            JobStageOut(
                id=s.id,
                type=s.type.value,
                status=s.status.value,
                order=s.order,
                started_at=s.started_at,
                finished_at=s.finished_at,
                error_message=s.error_message,
            )
            for s in sorted(job.stages, key=lambda s: s.order)
        ],
        artifacts=[
            ArtifactOut(
                id=a.id,
                kind=a.kind.value,
                filename=a.filename,
                size_bytes=a.size_bytes,
                duration=a.duration,
                mime_type=a.mime_type,
                download_url=f"/files/{a.filename}" if a.filename else None,
                file_exists=os.path.exists(a.path) if a.path else False,
                created_at=a.created_at,
            )
            for a in job.artifacts
        ],
        request=JobRequestOut(
            format_mode=job.request.format_mode,
            format_spec=job.request.format_spec,
            container=job.request.container,
            max_height=job.request.max_height,
            sponsorblock_action=job.request.sponsorblock_action.value,
            output_dir=job.request.output_dir,
        ) if job.request else None,
    )


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Cancel a pending or running job."""
    result = await db.execute(select(Job).where(Job.id == job_id).options(selectinload(Job.entry)))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
        raise HTTPException(status_code=409, detail=f"Job already {job.status.value}")

    # Revoke celery task if running
    if job.celery_task_id:
        from app.celery_app import celery
        celery.control.revoke(job.celery_task_id, terminate=True)

    job.status = JobStatus.CANCELLED
    await db.flush()

    return _job_to_out(job)


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retry a failed job from the first failed or pending stage."""
    result = await db.execute(
        select(Job).where(Job.id == job_id).options(
            selectinload(Job.entry),
            selectinload(Job.stages),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    # Reset failed stages to pending
    for stage in job.stages:
        if stage.status == StageStatus.FAILED:
            stage.status = StageStatus.PENDING
            stage.error_message = None
            stage.started_at = None
            stage.finished_at = None

    job.status = JobStatus.QUEUED
    job.error_code = None
    job.error_message = None
    await db.flush()

    # Dispatch first pending stage
    first_pending = sorted(
        [s for s in job.stages if s.status == StageStatus.PENDING],
        key=lambda s: s.order,
    )
    if first_pending:
        from app.worker.tasks import run_stage
        celery_result = run_stage.delay(str(job.id), str(first_pending[0].id))
        job.celery_task_id = celery_result.id
        await db.flush()

    return _job_to_out(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a job and its stages/artifacts from the database."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Cannot delete a running job — cancel it first")
    await db.delete(job)
    await db.flush()


class BulkDeleteRequest(PydanticBaseModel):
    job_ids: list[str]


@router.post("/bulk-delete", status_code=200)
async def bulk_delete_jobs(
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple jobs by ID. Skips running jobs."""
    if not body.job_ids:
        return {"deleted": 0, "skipped": 0}

    # Parse UUIDs safely
    parsed_ids = []
    for jid in body.job_ids:
        try:
            parsed_ids.append(uuid.UUID(jid))
        except ValueError:
            continue

    # Fetch all in one query
    result = await db.execute(select(Job).where(Job.id.in_(parsed_ids)))
    jobs = result.scalars().all()

    deleted = 0
    skipped = 0
    for job in jobs:
        if job.status == JobStatus.RUNNING:
            skipped += 1
            continue
        await db.delete(job)
        deleted += 1

    if deleted > 0:
        await db.flush()

    return {"deleted": deleted, "skipped": skipped}


def _job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        kind=job.kind.value,
        status=job.status.value,
        priority=job.priority,
        progress_pct=job.progress_pct,
        speed_bps=job.speed_bps,
        eta_seconds=job.eta_seconds,
        error_code=job.error_code,
        error_message=job.error_message,
        entry_id=job.entry_id,
        entry_title=job.entry.title if job.entry else None,
        entry_thumbnail=job.entry.thumbnail_url if job.entry else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
