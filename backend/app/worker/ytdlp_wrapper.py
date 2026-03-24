"""Contained yt-dlp adapter with download policy engine.

All yt-dlp interaction goes through this module. Pacing, throttle
detection, and concurrency are controlled by the concurrency mode
(safe/balanced/power).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

logger = logging.getLogger(__name__)

# ── Download policy profiles ───────────────────────────────────────────
# These control how aggressively yt-dlp downloads, matching the
# concurrency modes from the original architecture spec.

DOWNLOAD_PROFILES = {
    "safe": {
        # 1 active download, conservative pacing, browser-like behaviour
        "concurrent_fragment_downloads": 1,
        "sleep_requests": 1.5,          # seconds between HTTP requests
        "sleep_interval": 5,            # seconds between video downloads
        "max_sleep_interval": 30,       # max random sleep
        "throttled_rate": 100_000,      # bytes/s — re-extract if below this
        "ratelimit": None,              # no explicit rate limit
        "retries": 5,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "file_access_retries": 5,
        "socket_timeout": 30,
    },
    "balanced": {
        # 2-4 fragment concurrency, moderate pacing
        "concurrent_fragment_downloads": 3,
        "sleep_requests": 0.5,
        "sleep_interval": 2,
        "max_sleep_interval": 10,
        "throttled_rate": 100_000,
        "ratelimit": None,
        "retries": 3,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "file_access_retries": 3,
        "socket_timeout": 20,
    },
    "power": {
        # Maximum speed, user-enabled with warnings
        "concurrent_fragment_downloads": 5,
        "sleep_requests": 0,
        "sleep_interval": 0,
        "max_sleep_interval": 0,
        "throttled_rate": 100_000,
        "ratelimit": None,
        "retries": 3,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "file_access_retries": 3,
        "socket_timeout": 15,
    },
}


class YtdlpWrapper:
    def __init__(
        self,
        cookie_file: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        concurrency_mode: str = "balanced",
    ):
        self._cookie_file = cookie_file
        self._progress_callback = progress_callback
        self._profile = DOWNLOAD_PROFILES.get(concurrency_mode, DOWNLOAD_PROFILES["balanced"])

    def _base_opts(self) -> dict[str, Any]:
        profile = self._profile
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": False,
            "ignoreerrors": False,
            "noprogress": True,
            "no_color": True,
            # Retry settings from profile
            "retries": profile["retries"],
            "fragment_retries": profile["fragment_retries"],
            "file_access_retries": profile["file_access_retries"],
            "extractor_retries": profile["extractor_retries"],
            # Pacing — sleep between requests to avoid looking like a bot
            "sleep_requests": profile["sleep_requests"],
            "sleep_interval": profile["sleep_interval"],
            "max_sleep_interval": profile["max_sleep_interval"],
            # Throttle detection — if speed drops below this, yt-dlp
            # re-extracts the URL (YouTube sometimes serves slow CDN nodes)
            "throttled_rate": profile["throttled_rate"],
            # Fragment concurrency — how many chunks download in parallel
            "concurrent_fragment_downloads": profile["concurrent_fragment_downloads"],
            # Socket timeout
            "socket_timeout": profile["socket_timeout"],
        }
        # Explicit rate limit (if configured)
        if profile.get("ratelimit"):
            opts["ratelimit"] = profile["ratelimit"]
        if self._cookie_file:
            opts["cookiefile"] = self._cookie_file
        if self._progress_callback:
            opts["progress_hooks"] = [self._progress_callback]
        return opts

    def extract_info(self, url: str) -> dict[str, Any]:
        """Full metadata extraction without downloading. For single videos or playlists."""
        opts = {
            **self._base_opts(),
            "extract_flat": False,
            "format": "best/bestvideo+bestaudio/bestvideo/bestaudio",
            "ignore_no_formats_error": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ExtractorError(f"No info extracted for {url}")
            return ydl.sanitize_info(info)

    def extract_flat(self, url: str) -> dict[str, Any]:
        """Fast playlist/channel scan — returns entry list without per-video metadata."""
        opts = {**self._base_opts(), "extract_flat": "in_playlist"}
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ExtractorError(f"No info extracted for {url}")
            return ydl.sanitize_info(info)

    def download(
        self,
        url: str,
        format_spec: str,
        output_template: str,
    ) -> str:
        """Download a URL with the given format spec. Returns the output file path."""
        opts = {
            **self._base_opts(),
            "format": format_spec,
            "outtmpl": output_template,
            "overwrites": False,
            "continuedl": True,
        }
        _downloaded_path: list[str] = []

        def _postprocessor_hook(d: dict) -> None:
            if d.get("status") == "finished" and d.get("filename"):
                _downloaded_path.append(d["filename"])

        opts.setdefault("postprocessor_hooks", []).append(_postprocessor_hook)

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if _downloaded_path:
                return _downloaded_path[-1]
            if info is not None:
                return ydl.prepare_filename(info)
            raise DownloadError(f"Could not determine output path for {url}")
