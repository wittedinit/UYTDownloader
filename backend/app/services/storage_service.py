"""Storage management: retention policies and disk space protection."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Retention presets
RETENTION_PRESETS = {
    "1_day": timedelta(days=1),
    "1_week": timedelta(weeks=1),
    "1_month": timedelta(days=30),
    "3_months": timedelta(days=90),
    "6_months": timedelta(days=180),
    "1_year": timedelta(days=365),
    "forever": None,  # Never auto-delete
}

# Disk cleanup strategies
CLEANUP_STRATEGIES = {
    "oldest_first": "Delete oldest files first (by modification time)",
    "newest_first": "Delete newest files first (by modification time)",
    "largest_first": "Delete largest files first (free most space fastest)",
    "smallest_first": "Delete smallest files first (remove most files)",
}


def get_disk_usage() -> dict:
    """Get disk usage for the downloads directory."""
    output_dir = Path(settings.output_dir)
    try:
        usage = shutil.disk_usage(str(output_dir))
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        free_pct = (usage.free / usage.total * 100) if usage.total > 0 else 100

        # Calculate downloads folder size
        downloads_bytes = sum(
            f.stat().st_size for f in output_dir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        ) if output_dir.exists() else 0

        return {
            "disk_total_gb": round(total_gb, 2),
            "disk_used_gb": round(used_gb, 2),
            "disk_free_gb": round(free_gb, 2),
            "disk_free_pct": round(free_pct, 1),
            "downloads_bytes": downloads_bytes,
            "downloads_gb": round(downloads_bytes / (1024 ** 3), 2),
            "downloads_file_count": sum(1 for f in output_dir.iterdir() if f.is_file() and not f.name.startswith(".")) if output_dir.exists() else 0,
        }
    except Exception as e:
        logger.error("Failed to get disk usage: %s", e)
        return {"error": str(e)}


def enforce_retention(retention_key: str = "forever", dry_run: bool = False) -> dict:
    """
    Delete files older than the retention period.
    Returns list of files deleted (or that would be deleted if dry_run).
    """
    ttl = RETENTION_PRESETS.get(retention_key)
    if ttl is None:
        return {"deleted": [], "message": "Retention set to forever, nothing to delete"}

    output_dir = Path(settings.output_dir)
    if not output_dir.exists():
        return {"deleted": [], "message": "Downloads directory does not exist"}

    cutoff = datetime.now(timezone.utc) - ttl
    cutoff_ts = cutoff.timestamp()

    to_delete = []
    for f in output_dir.iterdir():
        if f.is_file() and not f.name.startswith("."):
            if f.stat().st_mtime < cutoff_ts:
                to_delete.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified_at": f.stat().st_mtime,
                    "age_days": (datetime.now(timezone.utc).timestamp() - f.stat().st_mtime) / 86400,
                })

    if not dry_run:
        for item in to_delete:
            try:
                (output_dir / item["filename"]).unlink()
                logger.info("Retention: deleted %s (age: %.1f days)", item["filename"], item["age_days"])
            except OSError as e:
                logger.error("Failed to delete %s: %s", item["filename"], e)

    freed_bytes = sum(item["size_bytes"] for item in to_delete)
    return {
        "deleted": to_delete,
        "count": len(to_delete),
        "freed_bytes": freed_bytes,
        "freed_gb": round(freed_bytes / (1024 ** 3), 2),
        "dry_run": dry_run,
        "retention": retention_key,
    }


def enforce_disk_guard(
    min_free_pct: float = 10.0,
    strategy: str = "oldest_first",
    dry_run: bool = False,
) -> dict:
    """
    Delete files when free disk space drops below threshold.
    Continues deleting until free space is above threshold or no files remain.
    """
    output_dir = Path(settings.output_dir)
    if not output_dir.exists():
        return {"deleted": [], "message": "Downloads directory does not exist"}

    usage = shutil.disk_usage(str(output_dir))
    free_pct = (usage.free / usage.total * 100) if usage.total > 0 else 100

    if free_pct >= min_free_pct:
        return {
            "deleted": [],
            "message": f"Disk has {free_pct:.1f}% free (threshold: {min_free_pct}%), no cleanup needed",
            "disk_free_pct": round(free_pct, 1),
        }

    # Get all files sorted by strategy
    files = []
    for f in output_dir.iterdir():
        if f.is_file() and not f.name.startswith("."):
            stat = f.stat()
            files.append({
                "path": f,
                "filename": f.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            })

    # Sort by strategy
    if strategy == "oldest_first":
        files.sort(key=lambda f: f["modified_at"])  # oldest first
    elif strategy == "newest_first":
        files.sort(key=lambda f: f["modified_at"], reverse=True)  # newest first
    elif strategy == "largest_first":
        files.sort(key=lambda f: f["size_bytes"], reverse=True)  # largest first
    elif strategy == "smallest_first":
        files.sort(key=lambda f: f["size_bytes"])  # smallest first

    deleted = []
    target_free = usage.total * (min_free_pct / 100)
    current_free = usage.free

    for item in files:
        if current_free >= target_free:
            break

        if not dry_run:
            try:
                item["path"].unlink()
                logger.info(
                    "Disk guard: deleted %s (%s, strategy=%s)",
                    item["filename"],
                    _format_bytes(item["size_bytes"]),
                    strategy,
                )
            except OSError as e:
                logger.error("Failed to delete %s: %s", item["filename"], e)
                continue

        current_free += item["size_bytes"]
        deleted.append({
            "filename": item["filename"],
            "size_bytes": item["size_bytes"],
        })

    freed_bytes = sum(d["size_bytes"] for d in deleted)
    new_free_pct = (current_free / usage.total * 100) if usage.total > 0 else 100

    return {
        "deleted": deleted,
        "count": len(deleted),
        "freed_bytes": freed_bytes,
        "freed_gb": round(freed_bytes / (1024 ** 3), 2),
        "disk_free_pct_before": round(free_pct, 1),
        "disk_free_pct_after": round(new_free_pct, 1),
        "strategy": strategy,
        "min_free_pct": min_free_pct,
        "dry_run": dry_run,
    }


def _format_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    if b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.1f} MB"
    return f"{b / (1024 * 1024 * 1024):.2f} GB"
