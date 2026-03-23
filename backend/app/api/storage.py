"""Storage management API: retention policies, disk space guard, usage stats."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.storage_service import (
    CLEANUP_STRATEGIES,
    RETENTION_PRESETS,
    enforce_disk_guard,
    enforce_retention,
    get_disk_usage,
)

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.get("/usage")
async def disk_usage():
    """Get disk usage stats for the downloads volume."""
    return get_disk_usage()


@router.get("/presets")
async def get_presets():
    """Get available retention presets and cleanup strategies."""
    return {
        "retention_presets": [
            {"key": k, "label": k.replace("_", " ").title(), "is_forever": v is None}
            for k, v in RETENTION_PRESETS.items()
        ],
        "cleanup_strategies": [
            {"key": k, "description": v}
            for k, v in CLEANUP_STRATEGIES.items()
        ],
    }


@router.post("/retention")
async def run_retention(
    retention: str = Query("forever", description="Retention preset: 1_day, 1_week, 1_month, 3_months, 6_months, 1_year, forever"),
    dry_run: bool = Query(False, description="Preview what would be deleted without actually deleting"),
):
    """
    Enforce retention policy — delete files older than the specified period.
    Use dry_run=true to preview without deleting.
    """
    if retention not in RETENTION_PRESETS:
        return {"error": f"Unknown retention preset: {retention}. Options: {list(RETENTION_PRESETS.keys())}"}
    return enforce_retention(retention, dry_run=dry_run)


@router.post("/disk-guard")
async def run_disk_guard(
    min_free_pct: float = Query(10.0, ge=1.0, le=50.0, description="Minimum free disk space percentage"),
    strategy: str = Query("oldest_first", description="Cleanup strategy: oldest_first, newest_first, largest_first, smallest_first"),
    dry_run: bool = Query(False, description="Preview what would be deleted without actually deleting"),
):
    """
    Enforce disk space guard — delete files when free space drops below threshold.
    Use dry_run=true to preview without deleting.
    """
    if strategy not in CLEANUP_STRATEGIES:
        return {"error": f"Unknown strategy: {strategy}. Options: {list(CLEANUP_STRATEGIES.keys())}"}
    return enforce_disk_guard(min_free_pct=min_free_pct, strategy=strategy, dry_run=dry_run)
