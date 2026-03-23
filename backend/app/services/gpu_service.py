"""GPU detection and ffmpeg encoder selection.

Priority: NVIDIA NVENC > Apple VideoToolbox > VA-API > CPU (libx264).
Falls back gracefully — no GPU means CPU-only transcoding.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def detect_gpu() -> dict:
    """
    Detect available GPU hardware acceleration for ffmpeg.
    Returns dict with encoder/decoder recommendations.
    """
    result = {
        "gpu_available": False,
        "gpu_type": None,
        "video_encoder": "copy",  # default: stream copy (no re-encode)
        "video_encoder_transcode": "libx264",  # fallback for re-encode
        "hwaccel": None,
        "hwaccel_device": None,
        "platform": platform.system(),
    }

    # Check for NVIDIA GPU (Linux/Windows)
    if _check_nvidia():
        result.update({
            "gpu_available": True,
            "gpu_type": "nvidia",
            "video_encoder_transcode": "h264_nvenc",
            "hwaccel": "cuda",
        })
        logger.info("NVIDIA GPU detected — using NVENC for transcoding")
        return result

    # Check for Apple VideoToolbox (macOS Metal)
    if _check_videotoolbox():
        result.update({
            "gpu_available": True,
            "gpu_type": "apple_metal",
            "video_encoder_transcode": "h264_videotoolbox",
            "hwaccel": "videotoolbox",
        })
        logger.info("Apple VideoToolbox detected — using Metal for transcoding")
        return result

    # Check for VA-API (Intel/AMD on Linux)
    if _check_vaapi():
        result.update({
            "gpu_available": True,
            "gpu_type": "vaapi",
            "video_encoder_transcode": "h264_vaapi",
            "hwaccel": "vaapi",
            "hwaccel_device": "/dev/dri/renderD128",
        })
        logger.info("VA-API GPU detected — using VA-API for transcoding")
        return result

    logger.info("No GPU detected — using CPU (libx264) for transcoding")
    return result


def _check_nvidia() -> bool:
    """Check if nvidia-smi is available and an NVIDIA GPU is present."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.debug("NVIDIA GPU: %s", result.stdout.strip())
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _check_videotoolbox() -> bool:
    """Check if Apple VideoToolbox is available (macOS with Metal GPU)."""
    if platform.system() != "Darwin":
        return False

    # Check if ffmpeg supports videotoolbox
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=5,
        )
        if "h264_videotoolbox" in result.stdout:
            logger.debug("VideoToolbox encoder available in ffmpeg")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _check_vaapi() -> bool:
    """Check if VA-API render device exists."""
    from pathlib import Path
    return Path("/dev/dri/renderD128").exists()


def build_ffmpeg_cmd(
    inputs: list[str],
    output: str,
    codec: str = "copy",
    extra_input_args: list[str] | None = None,
    extra_output_args: list[str] | None = None,
    filter_complex: str | None = None,
    maps: list[str] | None = None,
) -> list[str]:
    """
    Build an ffmpeg command with GPU acceleration when available and needed.
    codec="copy" means stream copy (no GPU needed).
    codec="transcode" means use GPU encoder if available.
    """
    gpu = detect_gpu()

    cmd = ["ffmpeg", "-y"]

    # Add hardware acceleration for input decoding if transcoding
    if codec == "transcode" and gpu["hwaccel"]:
        cmd.extend(["-hwaccel", gpu["hwaccel"]])
        if gpu["hwaccel_device"]:
            cmd.extend(["-hwaccel_device", gpu["hwaccel_device"]])

    # Add inputs
    for inp in inputs:
        if extra_input_args:
            cmd.extend(extra_input_args)
        cmd.extend(["-i", inp])

    # Filter complex
    if filter_complex:
        cmd.extend(["-filter_complex", filter_complex])

    # Maps
    if maps:
        for m in maps:
            cmd.extend(["-map", m])

    # Codec selection
    if codec == "copy":
        cmd.extend(["-c", "copy"])
    elif codec == "transcode":
        encoder = gpu["video_encoder_transcode"]
        cmd.extend(["-c:v", encoder, "-c:a", "aac"])

        # Encoder-specific quality settings
        if encoder == "h264_nvenc":
            cmd.extend(["-preset", "p4", "-rc", "vbr", "-cq", "23"])
        elif encoder == "h264_videotoolbox":
            # Apple VideoToolbox — quality-based encoding
            cmd.extend(["-q:v", "65"])
        elif encoder == "h264_vaapi":
            cmd.extend(["-qp", "23"])
        else:
            # CPU x264
            cmd.extend(["-preset", "medium", "-crf", "23"])

    # Extra output args
    if extra_output_args:
        cmd.extend(extra_output_args)

    cmd.extend(["-movflags", "+faststart", output])
    return cmd


def get_gpu_info() -> dict:
    """Return GPU info for health/diagnostics endpoint."""
    return detect_gpu()
