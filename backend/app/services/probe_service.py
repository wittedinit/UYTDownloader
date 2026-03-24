"""Probe service: extract metadata via yt-dlp, persist Source + Entry + SourceEntry + FormatSnapshot."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import EntryAvailability, SourceType
from app.models.entry import Entry
from app.models.format_snapshot import FormatSnapshot
from app.models.source import Source
from app.models.source_entry import SourceEntry
from app.worker.ytdlp_wrapper import YtdlpWrapper

logger = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    """Get a synchronous DB session for use in Celery workers."""
    from app.sync_db import get_sync_session
    return get_sync_session()


def _classify_source_type(info: dict) -> SourceType:
    yt_type = info.get("_type", "")
    if yt_type == "playlist":
        # Distinguish playlist from channel
        extractor = info.get("extractor", "").lower()
        if "channel" in extractor or "user" in extractor:
            return SourceType.CHANNEL
        return SourceType.PLAYLIST
    return SourceType.VIDEO


def _determine_availability(entry_info: dict) -> EntryAvailability:
    if entry_info.get("availability") == "needs_auth":
        return EntryAvailability.NEEDS_AUTH
    if entry_info.get("availability") == "private":
        return EntryAvailability.PRIVATE
    if entry_info.get("is_live"):
        return EntryAvailability.AVAILABLE
    return EntryAvailability.AVAILABLE


def _normalize_url(url: str, video_id: str | None = None) -> str:
    """Return canonical YouTube URL for a video ID."""
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def execute_probe(url: str, source_id: str | None = None) -> dict:
    """
    Main probe execution. Called from Celery task.
    Returns {source_id, entry_count, status}.
    """
    cookie_path = settings.cookie_path
    wrapper = YtdlpWrapper(
        cookie_file=str(cookie_path) if cookie_path else None,
        concurrency_mode=settings.concurrency_mode,
    )

    # Extract metadata
    logger.info("Probing URL: %s", url)
    info = wrapper.extract_info(url)

    source_type = _classify_source_type(info)
    is_playlist = source_type in (SourceType.PLAYLIST, SourceType.CHANNEL)

    if is_playlist:
        raw_entries = info.get("entries") or []
        # entries may be generators; materialize
        raw_entries = list(raw_entries)
    else:
        raw_entries = [info]

    # Persist to DB
    session = _get_sync_session()
    try:
        # Upsert Source
        source = _upsert_source(session, info, url, source_type, source_id)

        # Upsert Entries + SourceEntry + FormatSnapshot
        entry_count = 0
        for position, raw_entry in enumerate(raw_entries):
            if raw_entry is None:
                continue
            _upsert_entry(session, source, raw_entry, position, is_playlist)
            entry_count += 1

        source.entry_count = entry_count
        source.last_scanned_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(
            "Probe completed: source=%s type=%s entries=%d",
            source.id,
            source_type.value,
            entry_count,
        )
        return {
            "status": "completed",
            "source_id": str(source.id),
            "entry_count": entry_count,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _upsert_source(
    session: Session,
    info: dict,
    url: str,
    source_type: SourceType,
    existing_source_id: str | None,
) -> Source:
    """Find or create a Source record."""
    external_id = info.get("id") or info.get("channel_id") or ""
    canonical_url = info.get("webpage_url") or url

    # Try to find existing source
    if existing_source_id:
        source = session.get(Source, uuid.UUID(existing_source_id))
        if source:
            source.title = info.get("title") or source.title
            source.uploader = info.get("uploader") or source.uploader
            source.thumbnail_url = info.get("thumbnail") or source.thumbnail_url
            return source

    stmt = select(Source).where(Source.canonical_url == canonical_url)
    source = session.execute(stmt).scalar_one_or_none()
    if source:
        source.title = info.get("title") or source.title
        source.uploader = info.get("uploader") or source.uploader
        source.thumbnail_url = info.get("thumbnail") or source.thumbnail_url
        return source

    source = Source(
        type=source_type,
        canonical_url=canonical_url,
        external_id=external_id,
        title=info.get("title"),
        uploader=info.get("uploader") or info.get("channel"),
        thumbnail_url=info.get("thumbnail"),
    )
    session.add(source)
    session.flush()
    return source


def _upsert_entry(
    session: Session,
    source: Source,
    raw_entry: dict,
    position: int,
    is_playlist: bool,
) -> Entry:
    """Find or create an Entry, link via SourceEntry, create FormatSnapshot."""
    video_id = raw_entry.get("id") or ""
    if not video_id:
        logger.warning("Entry missing video ID, skipping")
        return None  # type: ignore

    # Upsert Entry by external_video_id
    stmt = select(Entry).where(Entry.external_video_id == video_id)
    entry = session.execute(stmt).scalar_one_or_none()

    title = raw_entry.get("title") or raw_entry.get("fulltitle") or "Untitled"
    duration = raw_entry.get("duration")
    upload_date = raw_entry.get("upload_date")
    thumbnail = raw_entry.get("thumbnail") or raw_entry.get("thumbnails", [{}])[-1].get("url") if raw_entry.get("thumbnails") else None
    availability = _determine_availability(raw_entry)

    # Store a subset of metadata (not the massive formats list)
    metadata = {
        k: raw_entry.get(k)
        for k in (
            "channel", "channel_id", "channel_url", "uploader", "uploader_id",
            "description", "categories", "tags", "view_count", "like_count",
            "age_limit", "is_live", "was_live", "live_status",
        )
        if raw_entry.get(k) is not None
    }

    if entry:
        entry.title = title
        entry.duration = duration
        entry.upload_date = upload_date
        entry.thumbnail_url = thumbnail or entry.thumbnail_url
        entry.availability = availability
        entry.metadata_json = metadata
    else:
        entry = Entry(
            external_video_id=video_id,
            title=title,
            duration=duration,
            upload_date=upload_date,
            thumbnail_url=thumbnail,
            availability=availability,
            metadata_json=metadata,
        )
        session.add(entry)
        session.flush()

    # Upsert SourceEntry join
    stmt = select(SourceEntry).where(
        SourceEntry.source_id == source.id,
        SourceEntry.entry_id == entry.id,
    )
    source_entry = session.execute(stmt).scalar_one_or_none()
    if not source_entry:
        source_entry = SourceEntry(
            source_id=source.id,
            entry_id=entry.id,
            position=position if is_playlist else None,
        )
        session.add(source_entry)

    # Create FormatSnapshot if formats available
    formats = raw_entry.get("formats")
    if formats:
        now = datetime.now(timezone.utc)
        snapshot = FormatSnapshot(
            entry_id=entry.id,
            fetched_at=now,
            expires_at=now + timedelta(seconds=settings.format_snapshot_ttl),
            formats_json=formats,
            subtitles_json=raw_entry.get("subtitles"),
            chapters_json=raw_entry.get("chapters"),
        )
        session.add(snapshot)

    return entry
