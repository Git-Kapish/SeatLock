"""Idempotency record model for non-replayable requests."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class IdempotencyKey(Base):
    """Stores idempotency cache entries to guarantee exactly-once execution."""

    __tablename__ = "idempotency_keys"
    __table_args__ = ({"schema": "booking"},)

    key: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    response_body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
