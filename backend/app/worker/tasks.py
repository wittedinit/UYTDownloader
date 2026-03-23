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
