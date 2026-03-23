"""Job service: create jobs, execute stages, manage lifecycle."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.archive import ArchiveRecord
from app.models.artifact import Artifact
from app.models.entry import Entry
from app.models.enums import (
    ArtifactKind,
    JobKind,
    JobStatus,
    SponsorBlockAction,
    StageStatus,
    StageType,
)
from app.models.job import Job, JobRequest, JobStage
from app.worker.ytdlp_wrapper import YtdlpWrapper

logger = logging.getLogger(__name__)

# ── Format resolution ──────────────────────────────────────────────────

QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio_only": "bestaudio/best",
}

CONTAINER_MAP = {
    "video_audio": "mp4",
    "audio_only": "m4a",
    "video_only": "mp4",
}


def _resolve_format_spec(format_mode: str, quality: str) -> str:
    if format_mode == "audio_only":
        return "bestaudio/best"
    if format_mode == "video_only":
        return "bestvideo/best"
    return QUALITY_MAP.get(quality, QUALITY_MAP["best"])


def _compute_output_signature(
    external_video_id: str, format_mode: str, quality: str, sponsorblock: str
) -> str:
    raw = f"{external_video_id}|{format_mode}|{quality}|{sponsorblock}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_max_height(quality: str) -> int | None:
    try:
        return int(quality.replace("p", ""))
    except (ValueError, AttributeError):
        return None


# ── Sync DB session ────────────────────────────────────────────────────

def _get_sync_session() -> Session:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    return factory()


# ── Job creation ───────────────────────────────────────────────────────

def _build_stages(
    format_mode: str,
    sponsorblock: str,
    embed_subs: bool = False,
    normalize: bool = False,
) -> list[dict]:
    """Return ordered list of stage definitions for a download job."""
    stages = [
        {"type": StageType.REVALIDATE_FORMATS, "order": 0},
    ]

    if format_mode == "audio_only":
        stages.append({"type": StageType.DOWNLOAD_AUDIO, "order": 1})
    elif format_mode == "video_only":
        stages.append({"type": StageType.DOWNLOAD_VIDEO, "order": 1})
    else:
        stages.append({"type": StageType.DOWNLOAD_VIDEO, "order": 1})
        stages.append({"type": StageType.DOWNLOAD_AUDIO, "order": 2})
        stages.append({"type": StageType.MERGE, "order": 3})

    if sponsorblock != "keep":
        next_order = max(s["order"] for s in stages) + 1
        stages.append({"type": StageType.SPONSORBLOCK, "order": next_order})

    if embed_subs:
        next_order = max(s["order"] for s in stages) + 1
        stages.append({"type": StageType.EMBED_SUBTITLES, "order": next_order})

    if normalize:
        next_order = max(s["order"] for s in stages) + 1
        stages.append({"type": StageType.NORMALIZE_AUDIO, "order": next_order})

    final_order = max(s["order"] for s in stages) + 1
    stages.append({"type": StageType.FINALIZE, "order": final_order})

    return stages


def create_jobs(
    entry_ids: list[uuid.UUID],
    format_mode: str = "video_audio",
    quality: str = "best",
    sponsorblock_action: str = "keep",
    output_dir: str | None = None,
    embed_subtitles: bool = False,
    normalize_audio: bool = False,
) -> list[dict]:
    """
    Create download jobs for the given entries.
    Returns list of job dicts suitable for API response.
    """
    session = _get_sync_session()
    try:
        format_spec = _resolve_format_spec(format_mode, quality)
        container = CONTAINER_MAP.get(format_mode, "mp4")
        max_height = _get_max_height(quality)
        cookie_path = settings.cookie_path
        out_dir = output_dir or str(settings.output_dir)

        created_jobs = []
        for entry_id in entry_ids:
            entry = session.get(Entry, entry_id)
            if not entry:
                logger.warning("Entry %s not found, skipping", entry_id)
                continue

            # Dedup check
            sig = _compute_output_signature(
                entry.external_video_id, format_mode, quality, sponsorblock_action
            )
            existing = session.execute(
                select(ArchiveRecord).where(
                    ArchiveRecord.external_video_id == entry.external_video_id,
                    ArchiveRecord.output_signature_hash == sig,
                )
            ).scalar_one_or_none()
            if existing:
                logger.info(
                    "Skipping %s — already archived with signature %s",
                    entry.external_video_id,
                    sig,
                )
                continue

            # Create job
            job = Job(kind=JobKind.DOWNLOAD, entry_id=entry.id, status=JobStatus.PENDING)
            session.add(job)
            session.flush()

            # Create immutable request
            req = JobRequest(
                job_id=job.id,
                format_mode=format_mode,
                format_spec=format_spec,
                container=container,
                max_height=max_height,
                sponsorblock_action=SponsorBlockAction(sponsorblock_action),
                output_dir=out_dir,
                cookie_file=str(cookie_path) if cookie_path else None,
                output_signature_hash=sig,
            )
            session.add(req)

            # Create stages
            stage_defs = _build_stages(format_mode, sponsorblock_action, embed_subtitles, normalize_audio)
            for sd in stage_defs:
                stage = JobStage(job_id=job.id, type=sd["type"], order=sd["order"])
                session.add(stage)

            session.flush()

            created_jobs.append({
                "id": str(job.id),
                "kind": job.kind.value,
                "status": job.status.value,
                "priority": job.priority,
                "progress_pct": job.progress_pct,
                "speed_bps": job.speed_bps,
                "eta_seconds": job.eta_seconds,
                "error_code": job.error_code,
                "error_message": job.error_message,
                "entry_id": str(entry.id),
                "entry_title": entry.title,
                "entry_thumbnail": entry.thumbnail_url,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            })

        session.commit()
        return created_jobs
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Stage execution ────────────────────────────────────────────────────

def execute_stage(job_id: str, stage_id: str, task=None) -> dict:
    """Execute a single stage. Called from Celery worker."""
    session = _get_sync_session()
    try:
        job = session.get(Job, uuid.UUID(job_id))
        stage = session.get(JobStage, uuid.UUID(stage_id))
        if not job or not stage:
            return {"status": "failed", "error": "Job or stage not found"}

        # Mark running
        job.status = JobStatus.RUNNING
        stage.status = StageStatus.RUNNING
        stage.started_at = datetime.now(timezone.utc)
        session.commit()

        # Dispatch to handler
        handlers = {
            StageType.REVALIDATE_FORMATS: _handle_revalidate,
            StageType.DOWNLOAD_VIDEO: _handle_download_video,
            StageType.DOWNLOAD_AUDIO: _handle_download_audio,
            StageType.MERGE: _handle_merge,
            StageType.SPONSORBLOCK: _handle_sponsorblock,
            StageType.EMBED_SUBTITLES: _handle_embed_subtitles,
            StageType.NORMALIZE_AUDIO: _handle_normalize_audio,
            StageType.FINALIZE: _handle_finalize,
        }
        handler = handlers.get(stage.type)
        if not handler:
            raise ValueError(f"Unknown stage type: {stage.type}")

        result = handler(session, job, stage, task)

        # Mark completed
        stage.status = StageStatus.COMPLETED
        stage.finished_at = datetime.now(timezone.utc)
        stage.result_json = result
        session.commit()

        # Dispatch next stage
        _dispatch_next_stage(session, job)

        return {"status": "completed", "result": result}

    except Exception as e:
        logger.error("Stage %s failed: %s", stage_id, e, exc_info=True)
        if stage:
            stage.status = StageStatus.FAILED
            stage.finished_at = datetime.now(timezone.utc)
            stage.error_message = str(e)
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
        session.commit()
        raise
    finally:
        session.close()


def _dispatch_next_stage(session: Session, job: Job):
    """Find and dispatch the next pending stage."""
    from app.worker.tasks import run_stage

    next_stage = session.execute(
        select(JobStage)
        .where(JobStage.job_id == job.id, JobStage.status == StageStatus.PENDING)
        .order_by(JobStage.order)
        .limit(1)
    ).scalar_one_or_none()

    if next_stage:
        celery_result = run_stage.delay(str(job.id), str(next_stage.id))
        job.celery_task_id = celery_result.id
        session.commit()
    else:
        # All stages done
        job.status = JobStatus.COMPLETED
        job.progress_pct = 100.0
        session.commit()


# ── Stage handlers ─────────────────────────────────────────────────────

def _get_wrapper(job: Job) -> YtdlpWrapper:
    req = job.request
    cookie = req.cookie_file if req else None

    def progress_hook(d: dict):
        # We could update job progress here via DB, but for now just log
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                logger.debug("Progress: %.1f%%", downloaded / total * 100)

    return YtdlpWrapper(cookie_file=cookie, progress_callback=progress_hook)


def _job_work_dir(job: Job) -> Path:
    d = settings.incomplete_dir / str(job.id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _video_url(entry: Entry) -> str:
    return f"https://www.youtube.com/watch?v={entry.external_video_id}"


def _handle_revalidate(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Re-extract format info to ensure we have fresh format data."""
    entry = job.entry
    if not entry:
        raise ValueError("Job has no entry")

    wrapper = _get_wrapper(job)
    info = wrapper.extract_info(_video_url(entry))

    formats = info.get("formats", [])
    logger.info("Revalidated %s: %d formats available", entry.external_video_id, len(formats))

    # Store in result for downstream stages
    return {
        "format_count": len(formats),
        "title": info.get("title"),
        "duration": info.get("duration"),
    }


def _handle_download_video(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Download the video stream."""
    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    wrapper = _get_wrapper(job)
    work_dir = _job_work_dir(job)

    # For video_only mode, use the full format spec. For video_audio, get just video.
    if req.format_mode == "video_only":
        fmt = req.format_spec
    else:
        fmt = "bestvideo"
        if req.max_height:
            fmt = f"bestvideo[height<={req.max_height}]"

    template = str(work_dir / "%(id)s.video.%(ext)s")
    output_path = wrapper.download(_video_url(entry), fmt, template)

    # Create artifact
    artifact = Artifact(
        job_id=job.id,
        kind=ArtifactKind.VIDEO_STREAM,
        path=output_path,
        filename=os.path.basename(output_path),
        size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
        produced_by_stage_id=stage.id,
    )
    session.add(artifact)
    session.flush()

    return {"path": output_path, "artifact_id": str(artifact.id)}


def _handle_download_audio(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Download the audio stream."""
    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    wrapper = _get_wrapper(job)
    work_dir = _job_work_dir(job)

    if req.format_mode == "audio_only":
        fmt = "bestaudio/best"
    else:
        fmt = "bestaudio"

    template = str(work_dir / "%(id)s.audio.%(ext)s")
    output_path = wrapper.download(_video_url(entry), fmt, template)

    artifact = Artifact(
        job_id=job.id,
        kind=ArtifactKind.AUDIO_STREAM,
        path=output_path,
        filename=os.path.basename(output_path),
        size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
        produced_by_stage_id=stage.id,
    )
    session.add(artifact)
    session.flush()

    return {"path": output_path, "artifact_id": str(artifact.id)}


def _handle_merge(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Merge video + audio streams via ffmpeg."""
    import subprocess

    work_dir = _job_work_dir(job)
    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    # Find video and audio artifacts
    video_artifact = session.execute(
        select(Artifact).where(
            Artifact.job_id == job.id, Artifact.kind == ArtifactKind.VIDEO_STREAM
        )
    ).scalar_one_or_none()
    audio_artifact = session.execute(
        select(Artifact).where(
            Artifact.job_id == job.id, Artifact.kind == ArtifactKind.AUDIO_STREAM
        )
    ).scalar_one_or_none()

    if not video_artifact or not audio_artifact:
        raise ValueError("Missing video or audio artifact for merge")

    container = req.container or "mp4"
    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in (entry.title or entry.external_video_id))
    output_path = str(work_dir / f"{safe_title}.{container}")

    from app.services.gpu_service import build_ffmpeg_cmd
    cmd = build_ffmpeg_cmd(
        inputs=[video_artifact.path, audio_artifact.path],
        output=output_path,
        codec="copy",
    )
    logger.info("Merging: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg merge failed: {result.stderr[-500:]}")

    merged = Artifact(
        job_id=job.id,
        kind=ArtifactKind.MERGED,
        path=output_path,
        filename=os.path.basename(output_path),
        size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
        produced_by_stage_id=stage.id,
        parent_artifact_id=video_artifact.id,
    )
    session.add(merged)
    session.flush()

    return {"path": output_path, "artifact_id": str(merged.id)}


def _handle_sponsorblock(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Apply SponsorBlock processing to the latest artifact."""
    from app.services.sponsorblock_service import apply_sponsorblock

    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    # Find the latest output artifact (merged > audio > video)
    source_artifact = None
    for kind in [ArtifactKind.MERGED, ArtifactKind.AUDIO_STREAM, ArtifactKind.VIDEO_STREAM]:
        source_artifact = session.execute(
            select(Artifact).where(Artifact.job_id == job.id, Artifact.kind == kind)
        ).scalar_one_or_none()
        if source_artifact:
            break

    if not source_artifact:
        raise ValueError("No source artifact for SponsorBlock processing")

    action = req.sponsorblock_action
    result = apply_sponsorblock(
        video_id=entry.external_video_id,
        input_path=source_artifact.path,
        action=action.value,
        api_url=settings.sponsorblock_api,
    )

    if result.get("output_path") and result["output_path"] != source_artifact.path:
        cleaned = Artifact(
            job_id=job.id,
            kind=ArtifactKind.CLEANED,
            path=result["output_path"],
            filename=os.path.basename(result["output_path"]),
            size_bytes=os.path.getsize(result["output_path"]) if os.path.exists(result["output_path"]) else None,
            produced_by_stage_id=stage.id,
            parent_artifact_id=source_artifact.id,
        )
        session.add(cleaned)
        session.flush()
        result["artifact_id"] = str(cleaned.id)

    return result


def _handle_embed_subtitles(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Embed subtitles into the latest artifact."""
    from app.services.postprocess_service import embed_subtitles

    entry = job.entry
    if not entry:
        raise ValueError("Job has no entry")

    # Get subtitle data from format snapshot
    from app.models.format_snapshot import FormatSnapshot
    snap = session.execute(
        select(FormatSnapshot)
        .where(FormatSnapshot.entry_id == entry.id)
        .order_by(FormatSnapshot.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    subtitles_json = snap.subtitles_json if snap else None
    if not subtitles_json:
        return {"embedded": False, "reason": "no subtitle data"}

    # Find latest artifact
    source_artifact = _find_latest_artifact(session, job)
    if not source_artifact:
        raise ValueError("No source artifact for subtitle embedding")

    result = embed_subtitles(source_artifact.path, subtitles_json)

    if result.get("embedded") and result.get("output_path"):
        artifact = Artifact(
            job_id=job.id,
            kind=ArtifactKind.SUBTITLED,
            path=result["output_path"],
            filename=os.path.basename(result["output_path"]),
            size_bytes=os.path.getsize(result["output_path"]) if os.path.exists(result["output_path"]) else None,
            produced_by_stage_id=stage.id,
            parent_artifact_id=source_artifact.id,
        )
        session.add(artifact)
        session.flush()
        result["artifact_id"] = str(artifact.id)

    return result


def _handle_normalize_audio(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Normalize audio loudness on the latest artifact."""
    from app.services.postprocess_service import normalize_audio

    source_artifact = _find_latest_artifact(session, job)
    if not source_artifact:
        raise ValueError("No source artifact for audio normalization")

    result = normalize_audio(source_artifact.path)

    if result.get("normalized") and result.get("output_path"):
        artifact = Artifact(
            job_id=job.id,
            kind=ArtifactKind.NORMALIZED,
            path=result["output_path"],
            filename=os.path.basename(result["output_path"]),
            size_bytes=result.get("size_bytes"),
            produced_by_stage_id=stage.id,
            parent_artifact_id=source_artifact.id,
        )
        session.add(artifact)
        session.flush()
        result["artifact_id"] = str(artifact.id)

    return result


def _find_latest_artifact(session: Session, job: Job) -> Artifact | None:
    """Find the most processed artifact for a job."""
    for kind in [ArtifactKind.NORMALIZED, ArtifactKind.SUBTITLED, ArtifactKind.CLEANED, ArtifactKind.MERGED, ArtifactKind.AUDIO_STREAM, ArtifactKind.VIDEO_STREAM]:
        artifact = session.execute(
            select(Artifact).where(Artifact.job_id == job.id, Artifact.kind == kind)
        ).scalar_one_or_none()
        if artifact:
            return artifact
    return None


def _handle_finalize(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Move final artifact to output directory and create archive record."""
    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    # Find the best final artifact
    final_artifact = _find_latest_artifact(session, job)

    if not final_artifact:
        raise ValueError("No artifact to finalize")

    # Move to output directory
    out_dir = Path(req.output_dir or str(settings.output_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / final_artifact.filename

    # Handle name collisions
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = out_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(final_artifact.path, str(dest))
    final_artifact.path = str(dest)
    final_artifact.filename = dest.name

    # Compute checksum
    sha256 = hashlib.sha256()
    with open(dest, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    final_artifact.checksum_sha256 = sha256.hexdigest()
    final_artifact.size_bytes = dest.stat().st_size

    # Create archive record
    archive = ArchiveRecord(
        external_video_id=entry.external_video_id,
        canonical_url=f"https://www.youtube.com/watch?v={entry.external_video_id}",
        output_signature_hash=req.output_signature_hash,
        artifact_id=final_artifact.id,
    )
    session.add(archive)

    # Clean up work directory
    work_dir = settings.incomplete_dir / str(job.id)
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)

    session.flush()

    return {
        "final_path": str(dest),
        "filename": dest.name,
        "size_bytes": final_artifact.size_bytes,
        "checksum": final_artifact.checksum_sha256,
    }
