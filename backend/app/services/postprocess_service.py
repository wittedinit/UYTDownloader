"""Post-processing: subtitle embedding, metadata cleanup, audio normalization."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def embed_subtitles(
    input_path: str,
    subtitles_json: dict | None,
    languages: list[str] | None = None,
) -> dict:
    """
    Download and embed subtitles into the media file.
    subtitles_json is the yt-dlp subtitles dict from FormatSnapshot.
    """
    if not subtitles_json:
        return {"embedded": False, "reason": "no subtitles available"}

    # Pick languages (default: en, then first available)
    target_langs = languages or ["en"]
    available = list(subtitles_json.keys())
    if not available:
        return {"embedded": False, "reason": "no subtitle tracks"}

    selected = []
    for lang in target_langs:
        if lang in subtitles_json:
            selected.append(lang)
    if not selected and available:
        selected = [available[0]]

    p = Path(input_path)
    output_path = str(p.parent / f"{p.stem}.subs{p.suffix}")

    # Download subtitle files
    sub_files = []
    for lang in selected:
        tracks = subtitles_json[lang]
        # Prefer srt, then vtt, then first available
        sub_url = None
        sub_ext = "srt"
        for track in tracks:
            if track.get("ext") == "srt":
                sub_url = track.get("url")
                sub_ext = "srt"
                break
            elif track.get("ext") == "vtt":
                sub_url = track.get("url")
                sub_ext = "vtt"
        if not sub_url and tracks:
            sub_url = tracks[0].get("url")
            sub_ext = tracks[0].get("ext", "srt")

        if sub_url:
            sub_path = str(p.parent / f"{p.stem}.{lang}.{sub_ext}")
            try:
                import httpx
                resp = httpx.get(sub_url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                with open(sub_path, "wb") as f:
                    f.write(resp.content)
                sub_files.append({"path": sub_path, "lang": lang})
            except Exception as e:
                logger.warning("Failed to download subtitle %s: %s", lang, e)

    if not sub_files:
        return {"embedded": False, "reason": "failed to download subtitles"}

    # Build ffmpeg command to embed subtitles
    cmd = ["ffmpeg", "-y", "-i", input_path]
    for sf in sub_files:
        cmd.extend(["-i", sf["path"]])

    cmd.extend(["-c", "copy"])
    for i, sf in enumerate(sub_files):
        cmd.extend(["-map", "0", "-map", str(i + 1)])
        cmd.extend([f"-metadata:s:s:{i}", f"language={sf['lang']}"])

    # Use mov_text for mp4, srt for mkv
    if p.suffix.lower() in (".mp4", ".m4v", ".m4a"):
        cmd.extend(["-c:s", "mov_text"])
    else:
        cmd.extend(["-c:s", "srt"])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    # Clean up downloaded subs
    for sf in sub_files:
        try:
            os.unlink(sf["path"])
        except OSError:
            pass

    if result.returncode != 0:
        logger.error("Subtitle embedding failed: %s", result.stderr[-300:])
        return {"embedded": False, "reason": result.stderr[-200:]}

    return {
        "embedded": True,
        "output_path": output_path,
        "languages": [sf["lang"] for sf in sub_files],
    }


def embed_thumbnail(input_path: str, thumbnail_url: str | None) -> dict:
    """Download and embed thumbnail as cover art."""
    if not thumbnail_url:
        return {"embedded": False, "reason": "no thumbnail URL"}

    p = Path(input_path)
    thumb_path = str(p.parent / f"{p.stem}.thumb.jpg")
    output_path = str(p.parent / f"{p.stem}.thumb{p.suffix}")

    try:
        import httpx
        resp = httpx.get(thumbnail_url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        with open(thumb_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        return {"embedded": False, "reason": f"download failed: {e}"}

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", thumb_path,
        "-map", "0", "-map", "1",
        "-c", "copy",
        "-disposition:v:1", "attached_pic",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    try:
        os.unlink(thumb_path)
    except OSError:
        pass

    if result.returncode != 0:
        return {"embedded": False, "reason": result.stderr[-200:]}

    return {"embedded": True, "output_path": output_path}


def normalize_audio(input_path: str, target_lufs: float = -16.0) -> dict:
    """
    Normalize audio loudness using ffmpeg loudnorm (EBU R128).
    Two-pass for accurate normalization.
    """
    p = Path(input_path)
    output_path = str(p.parent / f"{p.stem}.normalized{p.suffix}")

    # Pass 1: Analyze
    analyze_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    result = subprocess.run(analyze_cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        logger.error("Loudness analysis failed: %s", result.stderr[-300:])
        return {"normalized": False, "reason": "analysis failed"}

    # Parse loudnorm stats from stderr
    import json
    stderr = result.stderr
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        return {"normalized": False, "reason": "could not parse loudnorm output"}

    try:
        stats = json.loads(stderr[json_start:json_end])
    except json.JSONDecodeError:
        return {"normalized": False, "reason": "invalid loudnorm JSON"}

    measured_i = stats.get("input_i", "-24")
    measured_tp = stats.get("input_tp", "-1")
    measured_lra = stats.get("input_lra", "11")
    measured_thresh = stats.get("input_thresh", "-34")

    # Pass 2: Normalize
    norm_filter = (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:"
        f"measured_I={measured_i}:measured_TP={measured_tp}:"
        f"measured_LRA={measured_lra}:measured_thresh={measured_thresh}:"
        f"linear=true"
    )

    has_video = p.suffix.lower() in (".mp4", ".mkv", ".webm", ".m4v")
    if has_video:
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "copy",
            "-af", norm_filter,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", norm_filter,
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]

    result = subprocess.run(norm_cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        logger.error("Normalization failed: %s", result.stderr[-300:])
        return {"normalized": False, "reason": result.stderr[-200:]}

    return {
        "normalized": True,
        "output_path": output_path,
        "input_lufs": measured_i,
        "target_lufs": target_lufs,
        "size_bytes": os.path.getsize(output_path) if os.path.exists(output_path) else None,
    }
