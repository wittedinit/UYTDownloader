"""Storage management API: retention policies, disk space guard, usage stats, settings."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.storage_service import (
    CLEANUP_STRATEGIES,
    RETENTION_PRESETS,
    enforce_disk_guard,
    enforce_retention,
    get_disk_usage,
)
from app.worker.ytdlp_wrapper import DOWNLOAD_PROFILES

router = APIRouter(prefix="/api/storage", tags=["storage"])


# ── Response Models ───────────────────────────────────────────────────


class DiskUsageResponse(BaseModel):
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    disk_free_pct: Optional[float] = None
    downloads_bytes: Optional[int] = None
    downloads_gb: Optional[float] = None
    downloads_file_count: Optional[int] = None
    error: Optional[str] = None


class RetentionPresetItem(BaseModel):
    key: str
    label: str
    is_forever: bool


class CleanupStrategyItem(BaseModel):
    key: str
    description: str


class PresetsResponse(BaseModel):
    retention_presets: list[RetentionPresetItem]
    cleanup_strategies: list[CleanupStrategyItem]


class DeletedFileItem(BaseModel):
    filename: str
    size_bytes: int
    modified_at: Optional[float] = None
    age_days: Optional[float] = None


class RetentionResponse(BaseModel):
    deleted: list[DeletedFileItem]
    count: Optional[int] = None
    freed_bytes: Optional[int] = None
    freed_gb: Optional[float] = None
    dry_run: Optional[bool] = None
    retention: Optional[str] = None
    message: Optional[str] = None


class DiskGuardDeletedItem(BaseModel):
    filename: str
    size_bytes: int


class DiskGuardResponse(BaseModel):
    deleted: list[DiskGuardDeletedItem]
    count: Optional[int] = None
    freed_bytes: Optional[int] = None
    freed_gb: Optional[float] = None
    disk_free_pct_before: Optional[float] = None
    disk_free_pct_after: Optional[float] = None
    strategy: Optional[str] = None
    min_free_pct: Optional[float] = None
    dry_run: Optional[bool] = None
    message: Optional[str] = None
    disk_free_pct: Optional[float] = None


class ConcurrencyModeItem(BaseModel):
    key: str
    label: str
    description: str


class ActiveProfileFull(BaseModel):
    fragment_concurrency: int
    request_sleep: float
    download_sleep: float
    max_sleep: float
    throttle_detection_bps: int
    retries: int
    fragment_retries: int


class ConcurrencyModeResponse(BaseModel):
    mode: str
    available_modes: list[ConcurrencyModeItem]
    active_profile: ActiveProfileFull


class ActiveProfileBrief(BaseModel):
    fragment_concurrency: int
    request_sleep: float
    download_sleep: float


class SetConcurrencyModeResponse(BaseModel):
    mode: str
    active_profile: ActiveProfileBrief


@router.get("/usage", response_model=DiskUsageResponse)
async def disk_usage():
    """Get disk usage stats for the downloads volume."""
    return get_disk_usage()


@router.get("/presets", response_model=PresetsResponse)
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


@router.post("/retention", response_model=RetentionResponse)
async def run_retention(
    retention: str = Query("forever", description="Retention preset: 1_day, 1_week, 1_month, 3_months, 6_months, 1_year, forever"),
    dry_run: bool = Query(False, description="Preview what would be deleted without actually deleting"),
):
    """
    Enforce retention policy — delete files older than the specified period.
    Use dry_run=true to preview without deleting.
    """
    if retention not in RETENTION_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown retention preset: {retention}. Options: {list(RETENTION_PRESETS.keys())}")
    return enforce_retention(retention, dry_run=dry_run)


@router.post("/disk-guard", response_model=DiskGuardResponse)
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
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}. Options: {list(CLEANUP_STRATEGIES.keys())}")
    return enforce_disk_guard(min_free_pct=min_free_pct, strategy=strategy, dry_run=dry_run)


# ── Download Policy Settings ──────────────────────────────────────────

@router.get("/concurrency-mode", response_model=ConcurrencyModeResponse)
async def get_concurrency_mode():
    """Get current download concurrency mode and profile details."""
    mode = settings.concurrency_mode
    profile = DOWNLOAD_PROFILES.get(mode, DOWNLOAD_PROFILES["balanced"])
    return {
        "mode": mode,
        "available_modes": [
            {
                "key": "safe",
                "label": "Safe",
                "description": "1 fragment, 1.5s sleep — best for shared IPs, VPNs, or after being throttled",
            },
            {
                "key": "balanced",
                "label": "Balanced",
                "description": "3 fragments, 0.5s sleep — good default for most users",
            },
            {
                "key": "power",
                "label": "Power",
                "description": "5 fragments, no sleep — faster but higher risk of throttling",
            },
        ],
        "active_profile": {
            "fragment_concurrency": profile["concurrent_fragment_downloads"],
            "request_sleep": profile["sleep_requests"],
            "download_sleep": profile["sleep_interval"],
            "max_sleep": profile["max_sleep_interval"],
            "throttle_detection_bps": profile["throttled_rate"],
            "retries": profile["retries"],
            "fragment_retries": profile["fragment_retries"],
        },
    }


class ConcurrencyModeUpdate(BaseModel):
    mode: str


@router.put("/concurrency-mode", response_model=SetConcurrencyModeResponse)
async def set_concurrency_mode(body: ConcurrencyModeUpdate):
    """Update the download concurrency mode. Takes effect on the next download."""
    if body.mode not in DOWNLOAD_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode: {body.mode}. Options: {list(DOWNLOAD_PROFILES.keys())}",
        )
    # Update runtime settings
    settings.concurrency_mode = body.mode
    profile = DOWNLOAD_PROFILES[body.mode]
    return {
        "mode": body.mode,
        "active_profile": {
            "fragment_concurrency": profile["concurrent_fragment_downloads"],
            "request_sleep": profile["sleep_requests"],
            "download_sleep": profile["sleep_interval"],
        },
    }
