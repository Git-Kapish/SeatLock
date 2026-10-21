"""Processed webhook audit model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProcessedWebhook(Base):
    """Tracks received webhook event IDs for idempotency and replay protection."""

    __tablename__ = "processed_webhooks"
    __table_args__ = ({"schema": "booking"},)

    provider_event_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
