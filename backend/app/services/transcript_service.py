"""Transcript indexing service — extracts subtitles and indexes for full-text search."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.transcript import Transcript

logger = logging.getLogger(__name__)


def parse_vtt(vtt_text: str) -> str:
    """Extract plain text from WebVTT subtitle content."""
    lines = []
    for line in vtt_text.split("\n"):
        line = line.strip()
        # Skip headers, timestamps, empty lines
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"^\d{2}:\d{2}", line) or "-->" in line:
            continue
        if re.match(r"^\d+$", line):  # Sequence numbers
            continue
        # Strip HTML tags
        clean = re.sub(r"<[^>]+>", "", line)
        if clean:
            lines.append(clean)
    # Deduplicate consecutive identical lines (common in auto-captions)
    deduped = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return " ".join(deduped)


def parse_json3(json_text: str) -> str:
    """Extract plain text from YouTube JSON3 subtitle format."""
    try:
        data = json.loads(json_text)
        segments = data.get("events", [])
        texts = []
        for seg in segments:
            segs = seg.get("segs", [])
            for s in segs:
                t = s.get("utf8", "").strip()
                if t and t != "\n":
                    texts.append(t)
        return " ".join(texts)
    except (json.JSONDecodeError, KeyError):
        return ""


def extract_subtitles_from_info(info: dict) -> tuple[str, str]:
    """Try to get subtitle text from yt-dlp info dict.

    Returns (language, text). Prefers manual subs over auto-generated.
    """
    # Check for downloaded subtitle files
    requested_subtitles = info.get("requested_subtitles", {}) or {}
    for lang, sub_info in requested_subtitles.items():
        filepath = sub_info.get("filepath")
        if filepath and Path(filepath).exists():
            content = Path(filepath).read_text(errors="replace")
            ext = sub_info.get("ext", "vtt")
            if ext == "json3":
                return lang, parse_json3(content)
            return lang, parse_vtt(content)

    # Try subtitles from info dict directly
    subtitles = info.get("subtitles", {}) or {}
    auto_captions = info.get("automatic_captions", {}) or {}

    # Prefer English manual subs, then any manual, then English auto, then any auto
    for lang_pref in ["en", "en-US", "en-GB"]:
        if lang_pref in subtitles:
            return lang_pref, _extract_sub_text(subtitles[lang_pref])
        if lang_pref in auto_captions:
            return lang_pref, _extract_sub_text(auto_captions[lang_pref])

    # Any language
    if subtitles:
        lang = next(iter(subtitles))
        return lang, _extract_sub_text(subtitles[lang])
    if auto_captions:
        lang = next(iter(auto_captions))
        return lang, _extract_sub_text(auto_captions[lang])

    return "en", ""


def _extract_sub_text(sub_formats: list[dict]) -> str:
    """Extract text from subtitle format list."""
    for fmt in sub_formats:
        if fmt.get("ext") == "json3" and fmt.get("data"):
            return parse_json3(fmt["data"])
        if fmt.get("ext") == "vtt" and fmt.get("data"):
            return parse_vtt(fmt["data"])
    return ""


def index_transcript(
    session: Session,
    video_id: str,
    title: str,
    channel: str,
    language: str,
    content: str,
    entry_id: str | None = None,
) -> Transcript | None:
    """Store or update a transcript and update the search vector."""
    if not content or len(content.strip()) < 10:
        return None

    # Check for existing
    existing = session.query(Transcript).filter_by(video_id=video_id).first()
    if existing:
        existing.content = content
        existing.title = title or existing.title
        existing.channel = channel or existing.channel
        existing.language = language
        if entry_id:
            existing.entry_id = entry_id
        transcript = existing
    else:
        transcript = Transcript(
            video_id=video_id,
            title=title,
            channel=channel,
            language=language,
            content=content,
            entry_id=entry_id,
        )
        session.add(transcript)

    session.flush()

    # Update tsvector — combine title and content for search
    session.execute(
        text("""
            UPDATE transcripts
            SET search_vector =
                setweight(to_tsvector('english', coalesce(:title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(:channel, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(:content, '')), 'C')
            WHERE id = :tid
        """),
        {"title": title, "channel": channel, "content": content, "tid": str(transcript.id)},
    )
    session.commit()
    return transcript


def search_transcripts(
    session: Session,
    query: str,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Full-text search across all indexed transcripts."""
    if not query or not query.strip():
        return {"results": [], "total": 0, "query": query}

    # Build tsquery — handle multi-word queries
    words = query.strip().split()
    tsquery_str = " & ".join(words)

    # Count total matches
    count_result = session.execute(
        text("""
            SELECT count(*) FROM transcripts
            WHERE search_vector @@ to_tsquery('english', :q)
        """),
        {"q": tsquery_str},
    )
    total = count_result.scalar() or 0

    # Search with ranking and headline (snippet)
    results = session.execute(
        text("""
            SELECT
                id, video_id, title, channel, language,
                ts_rank(search_vector, to_tsquery('english', :q)) AS rank,
                ts_headline('english', content, to_tsquery('english', :q),
                    'StartSel=**, StopSel=**, MaxWords=40, MinWords=20, MaxFragments=3'
                ) AS snippet
            FROM transcripts
            WHERE search_vector @@ to_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :lim OFFSET :off
        """),
        {"q": tsquery_str, "lim": limit, "off": offset},
    )

    items = []
    for row in results:
        items.append({
            "id": str(row.id),
            "video_id": row.video_id,
            "title": row.title,
            "channel": row.channel,
            "language": row.language,
            "rank": float(row.rank),
            "snippet": row.snippet,
        })

    return {"results": items, "total": total, "query": query}
