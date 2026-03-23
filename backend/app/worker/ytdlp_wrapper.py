"""Contained yt-dlp adapter. All yt-dlp interaction goes through this module."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

logger = logging.getLogger(__name__)


class YtdlpWrapper:
    def __init__(
        self,
        cookie_file: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self._cookie_file = cookie_file
        self._progress_callback = progress_callback

    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": False,
            "ignoreerrors": False,
            "retries": 3,
            "fragment_retries": 5,
            "file_access_retries": 3,
            "extractor_retries": 3,
            "noprogress": True,
            "no_color": True,
        }
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
            # extract_info with download=True does both extraction and download in one call
            info = ydl.extract_info(url, download=True)
            if _downloaded_path:
                return _downloaded_path[-1]
            if info is not None:
                return ydl.prepare_filename(info)
            raise DownloadError(f"Could not determine output path for {url}")
