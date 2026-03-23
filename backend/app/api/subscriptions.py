"""Subscriptions API: create, list, get, update, delete, trigger check."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.enums import SubscriptionFilterType
from app.models.source import Source
from app.models.subscription import Subscription, SubscriptionFilter
from app.schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionDetail,
    SubscriptionFilterOut,
    SubscriptionListResponse,
    SubscriptionOut,
)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionDetail, status_code=201)
async def create_subscription(req: SubscriptionCreateRequest, db: AsyncSession = Depends(get_db)):
    """Create a subscription for a source (channel/playlist)."""
    source = await db.get(Source, req.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Check for existing subscription
    existing = await db.execute(
        select(Subscription).where(Subscription.source_id == req.source_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Subscription already exists for this source")

    sub = Subscription(
        source_id=req.source_id,
        check_interval_minutes=req.check_interval_minutes,
        auto_download=req.auto_download,
        format_mode=req.format_mode,
        quality=req.quality,
        sponsorblock_action=req.sponsorblock_action,
        next_check_at=datetime.now(timezone.utc) + timedelta(minutes=req.check_interval_minutes),
    )
    db.add(sub)
    await db.flush()

    # Add filters
    created_filters = []
    for f in req.filters:
        sf = SubscriptionFilter(
            subscription_id=sub.id,
            filter_type=SubscriptionFilterType(f.filter_type),
            value=f.value,
            enabled=f.enabled,
        )
        db.add(sf)
        created_filters.append(sf)

    await db.flush()

    return SubscriptionDetail(
        id=sub.id,
        source_id=sub.source_id,
        enabled=sub.enabled,
        check_interval_minutes=sub.check_interval_minutes,
        last_checked_at=sub.last_checked_at,
        next_check_at=sub.next_check_at,
        auto_download=sub.auto_download,
        format_mode=sub.format_mode,
        quality=sub.quality,
        sponsorblock_action=sub.sponsorblock_action,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        source_title=source.title,
        source_type=source.type.value,
        entry_count=source.entry_count,
        filters=[
            SubscriptionFilterOut(
                id=f.id,
                filter_type=f.filter_type.value,
                value=f.value,
                enabled=f.enabled,
            )
            for f in created_filters
        ],
    )


@router.get("", response_model=SubscriptionListResponse)
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    enabled: bool | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List all subscriptions."""
    query = select(Subscription).options(selectinload(Subscription.source))

    if enabled is not None:
        query = query.where(Subscription.enabled == enabled)

    count_q = select(func.count()).select_from(Subscription)
    if enabled is not None:
        count_q = count_q.where(Subscription.enabled == enabled)
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Subscription.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    subs = result.scalars().all()

    return SubscriptionListResponse(
        subscriptions=[_sub_to_out(s, s.source) for s in subs],
        total=total,
    )


@router.get("/{sub_id}", response_model=SubscriptionDetail)
async def get_subscription(sub_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get subscription details with filters."""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.id == sub_id)
        .options(selectinload(Subscription.source), selectinload(Subscription.filters))
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    source = sub.source  # Already eagerly loaded
    return _sub_to_detail(sub, source)


@router.patch("/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(
    sub_id: uuid.UUID,
    updates: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update subscription settings."""
    result = await db.execute(
        select(Subscription).where(Subscription.id == sub_id).options(selectinload(Subscription.source))
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    allowed = {"enabled", "check_interval_minutes", "auto_download", "format_mode", "quality", "sponsorblock_action"}
    for key, value in updates.items():
        if key in allowed:
            setattr(sub, key, value)

    await db.flush()
    source = sub.source  # Already loaded from prior query
    return _sub_to_out(sub, source)


@router.delete("/{sub_id}", status_code=204)
async def delete_subscription(sub_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a subscription."""
    result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.delete(sub)
    await db.flush()


@router.post("/{sub_id}/check", status_code=202)
async def trigger_check(sub_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Manually trigger a subscription check."""
    result = await db.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    from app.celery_app import celery
    from app.worker.tasks import check_subscription

    try:
        task = check_subscription.delay(str(sub_id))
    except Exception:
        try:
            celery.close()
            task = check_subscription.delay(str(sub_id))
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Queue unavailable: {e}")

    return {"task_id": task.id, "status": "checking"}


def _sub_to_out(sub: Subscription, source: Source | None = None) -> SubscriptionOut:
    if source is None:
        try:
            source = sub.source
        except Exception:
            source = None
    return SubscriptionOut(
        id=sub.id,
        source_id=sub.source_id,
        enabled=sub.enabled,
        check_interval_minutes=sub.check_interval_minutes,
        last_checked_at=sub.last_checked_at,
        next_check_at=sub.next_check_at,
        auto_download=sub.auto_download,
        format_mode=sub.format_mode,
        quality=sub.quality,
        sponsorblock_action=sub.sponsorblock_action,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        source_title=source.title if source else None,
        source_type=source.type.value if source else None,
        entry_count=source.entry_count if source else None,
    )


def _sub_to_detail(sub: Subscription, source: Source | None = None) -> SubscriptionDetail:
    out = _sub_to_out(sub, source)
    filters = []
    if hasattr(sub, "filters"):
        filters = [
            SubscriptionFilterOut(
                id=f.id,
                filter_type=f.filter_type.value,
                value=f.value,
                enabled=f.enabled,
            )
            for f in sub.filters
        ]
    return SubscriptionDetail(**out.model_dump(), filters=filters)
