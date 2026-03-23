"""Subscription service: check channels/playlists for new entries, auto-download."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entry import Entry
from app.models.source_entry import SourceEntry
from app.services.job_service import create_jobs

logger = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    from app.sync_db import get_sync_session
    return get_sync_session()


def check_subscription(subscription_id: str) -> dict:
    """
    Check a subscription for new entries.
    1. Re-probe the source URL
    2. Compare entries against what's already been downloaded
    3. Apply filters
    4. Auto-download matching entries if enabled
    """
    session = _get_sync_session()
    try:
        from app.models.subscription import Subscription, SubscriptionFilter
        from app.models.source import Source
        from app.models.archive import ArchiveRecord

        sub = session.get(Subscription, uuid.UUID(subscription_id))
        if not sub or not sub.enabled:
            return {"status": "skipped", "reason": "disabled or not found"}

        source = session.get(Source, sub.source_id)
        if not source:
            return {"status": "failed", "reason": "source not found"}

        # Re-probe the source
        from app.services.probe_service import execute_probe
        probe_result = execute_probe(source.canonical_url, source_id=str(source.id))

        if probe_result.get("status") != "completed":
            sub.last_checked_at = datetime.now(timezone.utc)
            sub.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=sub.check_interval_minutes)
            session.commit()
            return {"status": "failed", "reason": probe_result.get("error", "probe failed")}

        # Get all entries for this source
        entries = session.execute(
            select(Entry)
            .join(SourceEntry, SourceEntry.entry_id == Entry.id)
            .where(SourceEntry.source_id == source.id)
        ).scalars().all()

        # Apply filters
        filters = session.execute(
            select(SubscriptionFilter)
            .where(SubscriptionFilter.subscription_id == sub.id, SubscriptionFilter.enabled == True)
        ).scalars().all()

        filtered_entries = _apply_filters(entries, filters)

        # Find entries not yet archived with this subscription's settings
        new_entry_ids = []
        for entry in filtered_entries:
            from app.services.job_service import _compute_output_signature
            sig = _compute_output_signature(
                entry.external_video_id,
                sub.format_mode,
                sub.quality,
                sub.sponsorblock_action,
            )
            existing = session.execute(
                select(ArchiveRecord).where(
                    ArchiveRecord.external_video_id == entry.external_video_id,
                    ArchiveRecord.output_signature_hash == sig,
                )
            ).scalar_one_or_none()
            if not existing:
                new_entry_ids.append(entry.id)

        # Auto-download if enabled
        jobs_created = 0
        if sub.auto_download and new_entry_ids:
            created = create_jobs(
                entry_ids=new_entry_ids,
                format_mode=sub.format_mode,
                quality=sub.quality,
                sponsorblock_action=sub.sponsorblock_action,
            )
            jobs_created = len(created)

            # Dispatch first stage of each job
            from app.worker.tasks import run_stage
            from app.models.job import JobStage
            from app.models.enums import StageStatus

            for job_data in created:
                job_id = job_data["id"]
                first_stage = session.execute(
                    select(JobStage)
                    .where(
                        JobStage.job_id == uuid.UUID(job_id),
                        JobStage.status == StageStatus.PENDING,
                    )
                    .order_by(JobStage.order)
                    .limit(1)
                ).scalar_one_or_none()
                if first_stage:
                    run_stage.delay(job_id, str(first_stage.id))

        # Update subscription timestamps
        sub.last_checked_at = datetime.now(timezone.utc)
        sub.next_check_at = datetime.now(timezone.utc) + timedelta(minutes=sub.check_interval_minutes)
        session.commit()

        logger.info(
            "Subscription %s checked: %d entries, %d new, %d jobs created",
            subscription_id, len(entries), len(new_entry_ids), jobs_created,
        )
        return {
            "status": "completed",
            "total_entries": len(entries),
            "filtered_entries": len(filtered_entries),
            "new_entries": len(new_entry_ids),
            "jobs_created": jobs_created,
        }

    except Exception as e:
        logger.error("Subscription check failed for %s: %s", subscription_id, e, exc_info=True)
        session.rollback()
        return {"status": "failed", "reason": str(e)}
    finally:
        session.close()


def _apply_filters(entries: list[Entry], filters) -> list[Entry]:
    """Apply subscription filters to entry list."""
    from app.models.enums import SubscriptionFilterType

    result = list(entries)

    for f in filters:
        if f.filter_type == SubscriptionFilterType.IGNORE_SHORTS:
            # Shorts are typically < 60 seconds
            result = [e for e in result if not e.duration or e.duration >= 60]

        elif f.filter_type == SubscriptionFilterType.IGNORE_LIVE:
            result = [
                e for e in result
                if not (e.metadata_json or {}).get("is_live")
                and not (e.metadata_json or {}).get("was_live")
            ]

        elif f.filter_type == SubscriptionFilterType.MIN_DURATION:
            try:
                min_secs = float(f.value or "0")
                result = [e for e in result if not e.duration or e.duration >= min_secs]
            except ValueError:
                pass

        elif f.filter_type == SubscriptionFilterType.MAX_DURATION:
            try:
                max_secs = float(f.value or "999999")
                result = [e for e in result if not e.duration or e.duration <= max_secs]
            except ValueError:
                pass

        elif f.filter_type == SubscriptionFilterType.KEYWORD_INCLUDE:
            if f.value:
                keyword = f.value.lower()
                result = [e for e in result if keyword in (e.title or "").lower()]

        elif f.filter_type == SubscriptionFilterType.KEYWORD_EXCLUDE:
            if f.value:
                keyword = f.value.lower()
                result = [e for e in result if keyword not in (e.title or "").lower()]

    return result


def get_due_subscriptions() -> list[str]:
    """Get subscription IDs that are due for checking."""
    session = _get_sync_session()
    try:
        from app.models.subscription import Subscription
        now = datetime.now(timezone.utc)

        subs = session.execute(
            select(Subscription.id).where(
                Subscription.enabled == True,
                (Subscription.next_check_at == None) | (Subscription.next_check_at <= now),
            )
        ).scalars().all()

        return [str(s) for s in subs]
    finally:
        session.close()
