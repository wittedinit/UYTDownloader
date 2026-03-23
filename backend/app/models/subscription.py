import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SubscriptionFilterType


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    check_interval_minutes: Mapped[int] = mapped_column(default=360)
    last_checked_at: Mapped[datetime | None]
    next_check_at: Mapped[datetime | None]
    auto_download: Mapped[bool] = mapped_column(default=True)
    format_mode: Mapped[str] = mapped_column(String(64), default="video_audio")
    quality: Mapped[str] = mapped_column(String(64), default="best")
    sponsorblock_action: Mapped[str] = mapped_column(String(64), default="keep")

    source: Mapped["Source"] = relationship(back_populates="subscriptions")  # noqa: F821
    filters: Mapped[list["SubscriptionFilter"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class SubscriptionFilter(TimestampMixin, Base):
    __tablename__ = "subscription_filters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    filter_type: Mapped[SubscriptionFilterType]
    value: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(default=True)

    subscription: Mapped["Subscription"] = relationship(back_populates="filters")
