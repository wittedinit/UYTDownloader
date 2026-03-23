"""Celery task definitions. Thin dispatchers into service modules."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def run_probe(self, url: str, source_id: str | None = None) -> dict:
    """
    Extract metadata from URL without downloading.
    Persists Source + Entry + SourceEntry + FormatSnapshot.
    Returns {source_id, entry_count, status}.
    """
    from app.services.probe_service import execute_probe

    try:
        result = execute_probe(url, source_id=source_id)
        return result
    except Exception as e:
        logger.error("Probe failed for %s: %s", url, e, exc_info=True)
        # Retry on transient errors
        error_str = str(e).lower()
        retryable = any(
            kw in error_str
            for kw in ["429", "500", "503", "timeout", "connection", "temporary"]
        )
        if retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def check_subscription(self, subscription_id: str) -> dict:
    """Check a subscription for new content and auto-download if enabled."""
    from app.services.subscription_service import check_subscription as svc_check

    try:
        return svc_check(subscription_id)
    except Exception as e:
        logger.error("Subscription check failed for %s: %s", subscription_id, e, exc_info=True)
        error_str = str(e).lower()
        retryable = any(kw in error_str for kw in ["429", "timeout", "connection"])
        if retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@shared_task
def check_all_subscriptions() -> dict:
    """Periodic task: check all due subscriptions."""
    from app.services.subscription_service import get_due_subscriptions

    due = get_due_subscriptions()
    for sub_id in due:
        check_subscription.delay(sub_id)
    return {"checked": len(due)}


@shared_task
def run_storage_cleanup() -> dict:
    """Periodic task: enforce retention policy and disk space guard."""
    from app.config import settings
    from app.services.storage_service import enforce_retention, enforce_disk_guard

    results = {}

    if settings.retention != "forever":
        results["retention"] = enforce_retention(settings.retention)

    if settings.disk_guard_pct > 0:
        results["disk_guard"] = enforce_disk_guard(
            min_free_pct=settings.disk_guard_pct,
            strategy=settings.disk_guard_strategy,
        )

    return results


@shared_task(bind=True, max_retries=1, default_retry_delay=30)
def run_compilation(
    self,
    job_id: str,
    stage_id: str,
    input_files: list[dict],
    mode: str,
    normalize_audio: bool,
    title: str | None,
    output_dir: str | None,
) -> dict:
    """Execute a compilation (merge multiple files into one)."""
    import os
    import uuid
    from datetime import datetime, timezone
    from app.config import settings
    from app.services.compilation_service import build_compilation

    try:
        from app.services.job_service import _get_sync_session
        from app.models.job import Job, JobStage
        from app.models.artifact import Artifact
        from app.models.enums import ArtifactKind, JobStatus, StageStatus

        session = _get_sync_session()
        job = session.get(Job, uuid.UUID(job_id))
        stage = session.get(JobStage, uuid.UUID(stage_id))

        if job:
            job.status = JobStatus.RUNNING
        if stage:
            stage.status = StageStatus.RUNNING
            stage.started_at = datetime.now(timezone.utc)
        session.commit()

        # Build output path
        out_dir = output_dir or str(settings.output_dir)
        safe_title = title or "compilation"
        safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in safe_title)
        ext = ".m4a" if mode.startswith("audio_") else ".mp4"
        output_path = os.path.join(out_dir, f"{safe_title}{ext}")

        # Handle name collisions
        counter = 1
        base_path = output_path
        while os.path.exists(output_path):
            stem, suffix = os.path.splitext(base_path)
            output_path = f"{stem}_{counter}{suffix}"
            counter += 1

        result = build_compilation(input_files, output_path, mode, normalize_audio)

        if result.get("error"):
            if stage:
                stage.status = StageStatus.FAILED
                stage.error_message = result["error"]
                stage.finished_at = datetime.now(timezone.utc)
            if job:
                job.status = JobStatus.FAILED
                job.error_message = result["error"]
            session.commit()
            return {"status": "failed", "error": result["error"]}

        # Create artifact
        artifact = Artifact(
            job_id=job.id,
            kind=ArtifactKind.MERGED,
            path=result.get("output_path", output_path),
            filename=os.path.basename(result.get("output_path", output_path)),
            size_bytes=result.get("size_bytes"),
            produced_by_stage_id=stage.id if stage else None,
        )
        session.add(artifact)

        if stage:
            stage.status = StageStatus.COMPLETED
            stage.finished_at = datetime.now(timezone.utc)
            stage.result_json = result
        if job:
            job.status = JobStatus.COMPLETED
            job.progress_pct = 100.0
        session.commit()
        session.close()

        return {"status": "completed", "result": result}

    except Exception as e:
        logger.error("Compilation failed for job %s: %s", job_id, e, exc_info=True)
        try:
            session.rollback()
            session.close()
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def run_stage(self, job_id: str, stage_id: str) -> dict:
    """Execute one stage of a job. Triggers next stages on completion."""
    from app.services.job_service import execute_stage

    try:
        result = execute_stage(job_id, stage_id, task=self)
        return result
    except Exception as e:
        logger.error(
            "Stage %s failed for job %s: %s", stage_id, job_id, e, exc_info=True
        )
        error_str = str(e).lower()
        retryable = any(
            kw in error_str
            for kw in ["429", "500", "503", "timeout", "connection", "temporary"]
        )
        if retryable and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"status": "failed", "error": str(e)}
