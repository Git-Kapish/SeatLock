"""Repository for seat hold records and active reservations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hold import Hold, HoldSeat


class HoldRepository:
    """Encapsulates hold database queries and mutations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_hold(self, hold: Hold, hold_seats: list[HoldSeat]) -> Hold:
        """Persists a new hold record and its associated seat bindings."""
        self.session.add(hold)
        self.session.add_all(hold_seats)
        await self.session.flush()
        return hold

    async def get_hold_by_id(self, hold_id: uuid.UUID) -> Hold | None:
        """Retrieves a hold by ID including preloaded seats."""
        stmt = select(Hold).where(Hold.id == hold_id).options(selectinload(Hold.seats))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_hold_by_id(self, hold_id: uuid.UUID) -> Hold | None:
        """Retrieves a hold if it is currently 'active' and unexpired."""
        now = datetime.now(UTC)
        stmt = (
            select(Hold)
            .where(
                Hold.id == hold_id,
                Hold.status == "active",
                Hold.expires_at > now,
            )
            .options(selectinload(Hold.seats))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_active_holds_for_user(self, user_id: uuid.UUID) -> int:
        """Counts how many unexpired 'active' holds the user currently holds."""
        now = datetime.now(UTC)
        stmt = select(func.count(Hold.id)).where(
            Hold.user_id == user_id,
            Hold.status == "active",
            Hold.expires_at > now,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_hold_seat_ids(self, hold_id: uuid.UUID) -> list[uuid.UUID]:
        """Fetches list of seat IDs associated with a hold."""
        stmt = select(HoldSeat.seat_id).where(HoldSeat.hold_id == hold_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_expired_holds(self, current_time: datetime | None = None) -> Sequence[Hold]:
        """Finds active holds that have passed their expiration timestamp."""
        now = current_time or datetime.now(UTC)
        stmt = (
            select(Hold)
            .where(
                Hold.status == "active",
                Hold.expires_at <= now,
            )
            .options(selectinload(Hold.seats))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
