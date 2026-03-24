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
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "audio_only": "bestaudio/best",
    # Audio bitrate presets
    "audio_320k": "bestaudio[abr<=320]/bestaudio/best",
    "audio_256k": "bestaudio[abr<=256]/bestaudio/best",
    "audio_192k": "bestaudio[abr<=192]/bestaudio/best",
    "audio_128k": "bestaudio[abr<=128]/bestaudio/best",
    "audio_64k": "bestaudio[abr<=64]/bestaudio/best",
}

CONTAINER_MAP = {
    "video_audio": "mp4",
    "audio_only": "m4a",
    "video_only": "mp4",
}


def _resolve_format_spec(format_mode: str, quality: str) -> str:
    if format_mode == "audio_only":
        # Use audio-specific presets if provided, otherwise best audio
        return QUALITY_MAP.get(quality, "bestaudio/best")
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
    from app.sync_db import get_sync_session
    return get_sync_session()


# ── Job creation ───────────────────────────────────────────────────────

def _build_stages(
    format_mode: str,
    sponsorblock: str,
    embed_subs: bool = False,
    normalize: bool = False,
    output_format: str | None = None,
    playback_speed: float = 1.0,
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

    if output_format:
        next_order = max(s["order"] for s in stages) + 1
        stages.append({"type": StageType.REENCODE, "order": next_order})

    if playback_speed != 1.0:
        next_order = max(s["order"] for s in stages) + 1
        stages.append({"type": StageType.ADJUST_SPEED, "order": next_order})

    # Always embed metadata (title, artist, date, thumbnail) as the last
    # post-processing step before finalize
    next_order = max(s["order"] for s in stages) + 1
    stages.append({"type": StageType.EMBED_METADATA, "order": next_order})

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
    playback_speed: float = 1.0,
    output_format: str | None = None,
    video_bitrate: str | None = None,
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
        # Validate output_dir stays within configured output directory
        out_dir = str(settings.output_dir)
        if output_dir:
            resolved = Path(output_dir).resolve()
            allowed = Path(settings.output_dir).resolve()
            if resolved.is_relative_to(allowed):
                out_dir = str(resolved)
            else:
                logger.warning("Rejected output_dir %s — not within %s", output_dir, allowed)

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
                output_format=output_format,
                video_bitrate=video_bitrate,
                playback_speed=playback_speed,
                output_signature_hash=sig,
            )
            session.add(req)

            # Create stages
            stage_defs = _build_stages(format_mode, sponsorblock_action, embed_subtitles, normalize_audio, output_format, playback_speed)
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

        # Mark running — clear any previous error from failed attempts
        job.status = JobStatus.RUNNING
        job.error_message = None
        job.error_code = None
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
            StageType.REENCODE: _handle_reencode,
            StageType.EMBED_METADATA: _handle_embed_metadata,
            StageType.ADJUST_SPEED: _handle_adjust_speed,
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
        # All stages done — clear any leftover error from retried stages
        job.status = JobStatus.COMPLETED
        job.progress_pct = 100.0
        job.error_message = None
        job.error_code = None
        session.commit()


# ── Stage handlers ─────────────────────────────────────────────────────

def _update_job_progress(job_id: uuid.UUID, progress_pct: float, speed_bps: int | None, eta_seconds: int | None):
    """Write progress to DB. Called from yt-dlp progress hook."""
    from sqlalchemy import text
    from app.sync_db import sync_engine
    with sync_engine.connect() as conn:
        conn.execute(
            text("UPDATE jobs SET progress_pct = :pct, speed_bps = :speed, eta_seconds = :eta WHERE id = :id"),
            {"pct": progress_pct, "speed": speed_bps, "eta": eta_seconds, "id": str(job_id)},
        )
        conn.commit()


def _get_wrapper(job: Job) -> YtdlpWrapper:
    req = job.request
    cookie = req.cookie_file if req else None
    job_id = job.id
    _last_update = [0.0]  # Track last update time to avoid DB spam

    def progress_hook(d: dict):
        import time
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed")
            eta = d.get("eta")

            if total > 0:
                pct = min(downloaded / total * 100, 99.0)
                now = time.monotonic()
                # Update DB at most every 2 seconds
                if now - _last_update[0] >= 2.0:
                    _last_update[0] = now
                    try:
                        _update_job_progress(
                            job_id,
                            round(pct, 1),
                            int(speed) if speed else None,
                            int(eta) if eta else None,
                        )
                    except Exception:
                        pass  # Don't let progress updates kill the download

    return YtdlpWrapper(
        cookie_file=cookie,
        progress_callback=progress_hook,
        concurrency_mode=settings.concurrency_mode,
    )


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

    template = str(work_dir / "%(title)s.video.%(ext)s")
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

    template = str(work_dir / "%(title)s.audio.%(ext)s")
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
    for kind in [ArtifactKind.TAGGED, ArtifactKind.SPEED_ADJUSTED, ArtifactKind.REENCODED, ArtifactKind.NORMALIZED, ArtifactKind.SUBTITLED, ArtifactKind.CLEANED, ArtifactKind.MERGED, ArtifactKind.AUDIO_STREAM, ArtifactKind.VIDEO_STREAM]:
        artifact = session.execute(
            select(Artifact).where(Artifact.job_id == job.id, Artifact.kind == kind)
        ).scalar_one_or_none()
        if artifact:
            return artifact
    return None


def _handle_reencode(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Re-encode the latest artifact to a different format/bitrate."""
    import subprocess

    entry = job.entry
    req = job.request
    if not entry or not req:
        raise ValueError("Job missing entry or request")

    source_artifact = _find_latest_artifact(session, job)
    if not source_artifact:
        raise ValueError("No source artifact for re-encoding")

    output_format = req.output_format
    video_bitrate = req.video_bitrate
    if not output_format:
        return {"reencoded": False, "reason": "no output format specified"}

    # Map format names to ffmpeg parameters
    FORMAT_MAP = {
        "mp4_h264": {"ext": "mp4", "vcodec": "libx264", "acodec": "aac"},
        "mp4_h265": {"ext": "mp4", "vcodec": "libx265", "acodec": "aac"},
        "mkv_h264": {"ext": "mkv", "vcodec": "libx264", "acodec": "aac"},
        "webm_vp9": {"ext": "webm", "vcodec": "libvpx-vp9", "acodec": "libopus"},
        "mp3": {"ext": "mp3", "vcodec": None, "acodec": "libmp3lame"},
        "m4a_aac": {"ext": "m4a", "vcodec": None, "acodec": "aac"},
        "opus": {"ext": "opus", "vcodec": None, "acodec": "libopus"},
        "flac": {"ext": "flac", "vcodec": None, "acodec": "flac"},
    }

    fmt = FORMAT_MAP.get(output_format)
    if not fmt:
        return {"reencoded": False, "reason": f"unknown format: {output_format}"}

    work_dir = _job_work_dir(job)
    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in (entry.title or entry.external_video_id))
    output_path = str(work_dir / f"{safe_title}.reencoded.{fmt['ext']}")

    # Build ffmpeg command
    from app.services.gpu_service import detect_gpu
    gpu = detect_gpu()

    cmd = ["ffmpeg", "-y", "-i", source_artifact.path]

    if fmt["vcodec"]:
        # Check if GPU encoder is available for this codec
        encoder = fmt["vcodec"]
        if encoder == "libx264" and gpu["gpu_available"]:
            encoder = gpu["video_encoder_transcode"]
        cmd.extend(["-c:v", encoder])
        if video_bitrate:
            cmd.extend(["-b:v", video_bitrate])
        elif encoder in ("libx264", "libx265"):
            cmd.extend(["-crf", "23", "-preset", "medium"])
        elif encoder == "h264_nvenc":
            cmd.extend(["-preset", "p4", "-rc", "vbr", "-cq", "23"])
        elif encoder == "h264_videotoolbox":
            cmd.extend(["-q:v", "65"])
    else:
        cmd.extend(["-vn"])  # No video for audio-only formats

    cmd.extend(["-c:a", fmt["acodec"]])
    if fmt["acodec"] in ("aac", "libmp3lame", "libopus") and not fmt["vcodec"]:
        cmd.extend(["-b:a", "192k"])  # Default audio bitrate for audio-only

    if fmt["ext"] in ("mp4", "m4a"):
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(output_path)

    logger.info("Re-encoding to %s: %s", output_format, " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        raise RuntimeError(f"Re-encode failed: {result.stderr[-500:]}")

    artifact = Artifact(
        job_id=job.id,
        kind=ArtifactKind.REENCODED,
        path=output_path,
        filename=os.path.basename(output_path),
        size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
        produced_by_stage_id=stage.id,
        parent_artifact_id=source_artifact.id,
    )
    session.add(artifact)
    session.flush()

    return {
        "reencoded": True,
        "output_path": output_path,
        "format": output_format,
        "bitrate": video_bitrate,
        "artifact_id": str(artifact.id),
    }


def _handle_adjust_speed(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Adjust playback speed using ffmpeg atempo/setpts filters."""
    from app.services.postprocess_service import adjust_speed

    req = job.request
    if not req or req.playback_speed == 1.0:
        return {"adjusted": False, "reason": "no speed adjustment needed"}

    source_artifact = _find_latest_artifact(session, job)
    if not source_artifact:
        return {"adjusted": False, "reason": "no source artifact"}

    result = adjust_speed(source_artifact.path, req.playback_speed)

    if result.get("adjusted") and result.get("output_path"):
        artifact = Artifact(
            job_id=job.id,
            kind=ArtifactKind.SPEED_ADJUSTED,
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


def _handle_embed_metadata(session: Session, job: Job, stage: JobStage, task) -> dict:
    """Embed metadata tags (title, artist, date, thumbnail) into the media file."""
    from app.services.postprocess_service import embed_metadata

    entry = job.entry
    if not entry:
        return {"embedded": False, "reason": "no entry"}

    source_artifact = _find_latest_artifact(session, job)
    if not source_artifact:
        return {"embedded": False, "reason": "no source artifact"}

    # Extract metadata from entry
    meta = entry.metadata_json or {}
    thumbnail_url = meta.get("thumbnail") or meta.get("thumbnails", [{}])[-1].get("url")
    upload_date = entry.upload_date
    if upload_date:
        # Format as YYYY-MM-DD for tags
        date_str = upload_date.strftime("%Y-%m-%d") if hasattr(upload_date, "strftime") else str(upload_date)
    else:
        date_str = meta.get("upload_date")

    result = embed_metadata(
        input_path=source_artifact.path,
        title=entry.title,
        artist=meta.get("uploader") or meta.get("channel"),
        album=meta.get("playlist_title") or meta.get("channel"),
        date=date_str,
        description=meta.get("description"),
        thumbnail_url=thumbnail_url,
    )

    if result.get("embedded") and result.get("output_path"):
        artifact = Artifact(
            job_id=job.id,
            kind=ArtifactKind.TAGGED,
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
