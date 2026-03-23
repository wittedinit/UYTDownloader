"""Compilation builder: merge multiple videos/audios into one file with chapters."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.services.gpu_service import detect_gpu

logger = logging.getLogger(__name__)


def build_compilation(
    input_files: list[dict],
    output_path: str,
    mode: str = "video_chapters",
    normalize_audio: bool = False,
) -> dict:
    """
    Merge multiple media files into one compilation.

    input_files: list of {"path": str, "title": str, "duration": float}
    mode: "video_chapters" | "video_no_chapters" | "audio_chapters" | "audio_no_chapters"
    normalize_audio: whether to normalize loudness

    Returns: {"output_path": str, "duration": float, "chapters": int, "size_bytes": int}
    """
    if not input_files:
        return {"error": "no input files"}

    # Verify all inputs exist
    for f in input_files:
        if not os.path.exists(f["path"]):
            return {"error": f"input file not found: {f['path']}"}

    is_audio_only = mode.startswith("audio_")
    with_chapters = mode.endswith("_chapters")

    # Step 1: Create concat list file
    concat_list = _create_concat_list(input_files)

    # Step 2: Determine if we need re-encoding (different codecs/resolutions)
    needs_reencode = _check_needs_reencode(input_files)

    # Step 3: Build ffmpeg command
    if needs_reencode or is_audio_only:
        result = _compile_with_reencode(
            input_files, concat_list, output_path, is_audio_only, normalize_audio
        )
    else:
        result = _compile_with_concat(concat_list, output_path)

    # Clean up
    try:
        os.unlink(concat_list)
    except OSError:
        pass

    if result.get("error"):
        return result

    # Step 4: Add chapter metadata if requested
    if with_chapters and os.path.exists(output_path):
        chapter_result = _add_chapters(input_files, output_path)
        result["chapters"] = chapter_result.get("chapters", 0)
    else:
        result["chapters"] = 0

    result["size_bytes"] = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    return result


def _create_concat_list(input_files: list[dict]) -> str:
    """Create ffmpeg concat demuxer list file."""
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="uyt_concat_")
    with os.fdopen(fd, "w") as f:
        for item in input_files:
            # Escape single quotes in paths
            escaped = item["path"].replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    return path


def _check_needs_reencode(input_files: list[dict]) -> bool:
    """Check if files have different codecs/resolutions requiring re-encode."""
    if len(input_files) <= 1:
        return False

    codecs = set()
    resolutions = set()

    for f in input_files:
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height",
                "-of", "csv=p=0",
                f["path"],
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    codecs.add(parts[0])
                    resolutions.add(f"{parts[1]}x{parts[2]}")
        except (subprocess.TimeoutExpired, Exception):
            return True  # If we can't probe, assume re-encode needed

    return len(codecs) > 1 or len(resolutions) > 1


def _compile_with_concat(concat_list: str, output_path: str) -> dict:
    """Fast concat using stream copy (same codec/resolution)."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    logger.info("Compiling with concat (stream copy)")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        return {"error": f"concat failed: {result.stderr[-500:]}"}

    return {"output_path": output_path, "method": "concat_copy"}


def _compile_with_reencode(
    input_files: list[dict],
    concat_list: str,
    output_path: str,
    audio_only: bool,
    normalize: bool,
) -> dict:
    """Re-encode compilation for mixed sources or audio-only output."""
    gpu = detect_gpu()

    if audio_only:
        # Audio-only compilation
        filter_parts = []
        for i in range(len(input_files)):
            filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}];")

        filter_str = "".join(filter_parts)
        concat_inputs = "".join(f"[a{i}]" for i in range(len(input_files)))
        filter_str += f"{concat_inputs}concat=n={len(input_files)}:v=0:a=1[outa]"

        if normalize:
            filter_str += ";[outa]loudnorm=I=-16:TP=-1.5:LRA=11[outfinal]"
            map_label = "[outfinal]"
        else:
            map_label = "[outa]"

        cmd = ["ffmpeg", "-y"]
        for f in input_files:
            cmd.extend(["-i", f["path"]])
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", map_label,
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ])
    else:
        # Video + audio compilation with re-encode
        encoder = gpu["video_encoder_transcode"]

        filter_parts = []
        for i in range(len(input_files)):
            filter_parts.append(
                f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];"
            )
            filter_parts.append(
                f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}];"
            )

        filter_str = "".join(filter_parts)
        v_concat = "".join(f"[v{i}]" for i in range(len(input_files)))
        a_concat = "".join(f"[a{i}]" for i in range(len(input_files)))
        filter_str += f"{v_concat}concat=n={len(input_files)}:v=1:a=0[outv];"
        filter_str += f"{a_concat}concat=n={len(input_files)}:v=0:a=1[outa]"

        cmd = ["ffmpeg", "-y"]
        if gpu["hwaccel"]:
            cmd.extend(["-hwaccel", gpu["hwaccel"]])
        for f in input_files:
            cmd.extend(["-i", f["path"]])
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", encoder,
        ])

        # Encoder quality settings
        if encoder == "h264_nvenc":
            cmd.extend(["-preset", "p4", "-rc", "vbr", "-cq", "23"])
        elif encoder == "h264_videotoolbox":
            cmd.extend(["-q:v", "65"])
        elif encoder == "h264_vaapi":
            cmd.extend(["-qp", "23"])
        else:
            cmd.extend(["-preset", "medium", "-crf", "23"])

        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path])

    logger.info("Compiling with re-encode (%s)", "audio_only" if audio_only else gpu["video_encoder_transcode"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

    if result.returncode != 0:
        return {"error": f"re-encode failed: {result.stderr[-500:]}"}

    return {"output_path": output_path, "method": "reencode"}


def _add_chapters(input_files: list[dict], output_path: str) -> dict:
    """Add chapter metadata based on input file boundaries."""
    # Calculate chapter boundaries from durations
    chapters = []
    cursor = 0.0

    for item in input_files:
        duration = item.get("duration") or _probe_duration(item["path"])
        if duration and duration > 0:
            chapters.append({
                "start": cursor,
                "end": cursor + duration,
                "title": item.get("title", f"Chapter {len(chapters) + 1}"),
            })
            cursor += duration

    if not chapters:
        return {"chapters": 0}

    # Write metadata file
    meta_path = output_path + ".ffmeta"
    with open(meta_path, "w") as f:
        f.write(";FFMETADATA1\n")
        for ch in chapters:
            f.write("[CHAPTER]\n")
            f.write("TIMEBASE=1/1000\n")
            f.write(f"START={int(ch['start'] * 1000)}\n")
            f.write(f"END={int(ch['end'] * 1000)}\n")
            title = ch["title"].replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\\", "\\\\")
            f.write(f"title={title}\n")

    # Apply chapters — use a temp file in the same directory
    import tempfile
    out_dir = os.path.dirname(output_path)
    fd, chaptered_path = tempfile.mkstemp(suffix=os.path.splitext(output_path)[1], dir=out_dir)
    os.close(fd)
    cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-i", meta_path,
        "-map_metadata", "1",
        "-map_chapters", "1",
        "-map", "0",
        "-c", "copy",
        chaptered_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    try:
        os.unlink(meta_path)
    except OSError:
        pass

    if result.returncode == 0:
        os.replace(chaptered_path, output_path)
        return {"chapters": len(chapters)}
    else:
        try:
            os.unlink(chaptered_path)
        except OSError:
            pass
        logger.warning("Chapter embedding failed: %s", result.stderr[-200:])
        return {"chapters": 0}


def _probe_duration(path: str) -> float | None:
    """Get duration of a media file via ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip()) if result.stdout.strip() else None
    except (ValueError, subprocess.TimeoutExpired):
        return None
