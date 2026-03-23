"""SponsorBlock integration: fetch segments, apply mark/remove via ffmpeg."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# SponsorBlock categories to process
DEFAULT_CATEGORIES = [
    "sponsor",
    "selfpromo",
    "interaction",  # subscribe reminders
    "intro",
    "outro",
    "music_offtopic",
]


def fetch_segments(
    video_id: str,
    api_url: str = "https://sponsor.ajay.app",
    categories: list[str] | None = None,
) -> list[dict]:
    """Fetch SponsorBlock segments for a video."""
    cats = categories or DEFAULT_CATEGORIES
    params = {
        "videoID": video_id,
        "categories": json.dumps(cats),
    }
    try:
        resp = httpx.get(
            f"{api_url}/api/skipSegments",
            params=params,
            timeout=10.0,
        )
        if resp.status_code == 404:
            logger.info("No SponsorBlock segments for %s", video_id)
            return []
        resp.raise_for_status()
        segments = resp.json()
        logger.info("Found %d SponsorBlock segments for %s", len(segments), video_id)
        return segments
    except httpx.HTTPStatusError as e:
        logger.warning("SponsorBlock API error for %s: %s", video_id, e)
        return []
    except httpx.RequestError as e:
        logger.warning("SponsorBlock request failed for %s: %s", video_id, e)
        return []


def apply_sponsorblock(
    video_id: str,
    input_path: str,
    action: str = "remove",
    api_url: str = "https://sponsor.ajay.app",
    categories: list[str] | None = None,
) -> dict:
    """
    Apply SponsorBlock processing to a media file.
    action: "mark_chapters" | "remove"
    Returns dict with output_path, segments_found, segments_applied.
    """
    segments = fetch_segments(video_id, api_url, categories)

    if not segments:
        return {
            "output_path": input_path,
            "segments_found": 0,
            "segments_applied": 0,
            "action": action,
        }

    if action == "mark_chapters":
        return _mark_chapters(input_path, segments)
    elif action == "remove":
        return _remove_segments(input_path, segments)
    else:
        return {
            "output_path": input_path,
            "segments_found": len(segments),
            "segments_applied": 0,
            "action": "keep",
        }


def _mark_chapters(input_path: str, segments: list[dict]) -> dict:
    """Add chapter markers for sponsor segments via ffmpeg metadata."""
    # Get duration from ffprobe
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0

    if duration <= 0:
        return {"output_path": input_path, "segments_found": len(segments), "segments_applied": 0, "action": "mark_chapters"}

    # Build chapter metadata
    chapters = _build_chapter_metadata(segments, duration)

    # Write metadata file
    meta_path = input_path + ".ffmeta"
    with open(meta_path, "w") as f:
        f.write(";FFMETADATA1\n")
        for ch in chapters:
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={int(ch['start'] * 1000)}\n")
            f.write(f"END={int(ch['end'] * 1000)}\n")
            f.write(f"title={ch['title']}\n")

    # Apply metadata
    p = Path(input_path)
    output_path = str(p.parent / f"{p.stem}.chapters{p.suffix}")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", meta_path,
        "-map_metadata", "1",
        "-map_chapters", "1",
        "-c", "copy",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    os.unlink(meta_path)

    if proc.returncode != 0:
        logger.error("Chapter marking failed: %s", proc.stderr[-300:])
        return {"output_path": input_path, "segments_found": len(segments), "segments_applied": 0, "action": "mark_chapters"}

    return {
        "output_path": output_path,
        "segments_found": len(segments),
        "segments_applied": len(segments),
        "action": "mark_chapters",
        "chapters": len(chapters),
    }


def _remove_segments(input_path: str, segments: list[dict]) -> dict:
    """Remove sponsor segments by cutting them out with ffmpeg."""
    # Sort segments by start time
    time_ranges = sorted(
        [(s["segment"][0], s["segment"][1]) for s in segments],
        key=lambda x: x[0],
    )

    # Get total duration
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0

    if duration <= 0 or not time_ranges:
        return {"output_path": input_path, "segments_found": len(segments), "segments_applied": 0, "action": "remove"}

    # Build keep ranges (inverse of remove ranges)
    keep_ranges = []
    cursor = 0.0
    for start, end in time_ranges:
        if start > cursor:
            keep_ranges.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        keep_ranges.append((cursor, duration))

    if not keep_ranges:
        return {"output_path": input_path, "segments_found": len(segments), "segments_applied": 0, "action": "remove"}

    p = Path(input_path)
    output_path = str(p.parent / f"{p.stem}.cleaned{p.suffix}")

    # Detect if file has video stream
    has_video = False
    try:
        vprobe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries", "stream=codec_type",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=10,
        )
        has_video = "video" in vprobe.stdout.strip().lower()
    except Exception:
        pass

    # Build complex ffmpeg filter — audio-only or video+audio
    filter_parts = []
    concat_parts = []
    for i, (start, end) in enumerate(keep_ranges):
        if has_video:
            filter_parts.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];")
        filter_parts.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];")
        if has_video:
            concat_parts.append(f"[v{i}][a{i}]")
        else:
            concat_parts.append(f"[a{i}]")

    if has_video:
        filter_str = "".join(filter_parts) + "".join(concat_parts) + f"concat=n={len(keep_ranges)}:v=1:a=1[outv][outa]"
        maps = ["[outv]", "[outa]"]
    else:
        filter_str = "".join(filter_parts) + "".join(concat_parts) + f"concat=n={len(keep_ranges)}:v=0:a=1[outa]"
        maps = ["[outa]"]

    from app.services.gpu_service import build_ffmpeg_cmd
    cmd = build_ffmpeg_cmd(
        inputs=[input_path],
        output=output_path,
        codec="transcode",
        filter_complex=filter_str,
        maps=maps,
    )
    logger.info("Removing %d segments from %s", len(time_ranges), input_path)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if proc.returncode != 0:
        logger.error("Segment removal failed: %s", proc.stderr[-500:])
        return {"output_path": input_path, "segments_found": len(segments), "segments_applied": 0, "action": "remove"}

    return {
        "output_path": output_path,
        "segments_found": len(segments),
        "segments_applied": len(time_ranges),
        "action": "remove",
        "removed_seconds": sum(end - start for start, end in time_ranges),
    }


def _build_chapter_metadata(segments: list[dict], duration: float) -> list[dict]:
    """Build chapter markers from SponsorBlock segments."""
    # Sort by start time
    seg_times = sorted(
        [(s["segment"][0], s["segment"][1], s.get("category", "sponsor")) for s in segments],
        key=lambda x: x[0],
    )

    chapters = []
    cursor = 0.0

    for start, end, category in seg_times:
        if start > cursor:
            chapters.append({"start": cursor, "end": start, "title": "Content"})
        chapters.append({"start": start, "end": end, "title": f"[{category}]"})
        cursor = end

    if cursor < duration:
        chapters.append({"start": cursor, "end": duration, "title": "Content"})

    return chapters
