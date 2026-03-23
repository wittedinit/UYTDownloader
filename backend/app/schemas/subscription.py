from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SubscriptionFilterCreate(BaseModel):
    filter_type: str  # SubscriptionFilterType value
    value: str | None = None
    enabled: bool = True


class SubscriptionCreateRequest(BaseModel):
    source_id: uuid.UUID
    check_interval_minutes: int = 360
    auto_download: bool = True
    format_mode: str = "video_audio"
    quality: str = "best"
    sponsorblock_action: str = "keep"
    filters: list[SubscriptionFilterCreate] = []


class SubscriptionFilterOut(BaseModel):
    id: uuid.UUID
    filter_type: str
    value: str | None
    enabled: bool

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    enabled: bool
    check_interval_minutes: int
    last_checked_at: datetime | None
    next_check_at: datetime | None
    auto_download: bool
    format_mode: str
    quality: str
    sponsorblock_action: str
    created_at: datetime
    updated_at: datetime

    # Denormalized from source
    source_title: str | None = None
    source_type: str | None = None
    entry_count: int | None = None

    model_config = {"from_attributes": True}


class SubscriptionDetail(SubscriptionOut):
    filters: list[SubscriptionFilterOut] = []


class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionOut]
    total: int
