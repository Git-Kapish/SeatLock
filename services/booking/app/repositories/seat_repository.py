"""Repository for querying, locking, and bulk creating seat inventory."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seat import Seat


class SeatRepository:
    """Encapsulates seat inventory persistence with deadlock-free row locking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_seats_for_update(
        self,
        event_id: uuid.UUID,
        seat_ids: list[uuid.UUID],
    ) -> Sequence[Seat]:
        """Locks and fetches target seats ordered by seat_id ASC.

        Crucial: Sorting by seat_id ASC prevents deadlocks when concurrent
        transactions request intersecting sets of seats.
        """
        stmt = (
            select(Seat)
            .where(Seat.event_id == event_id, Seat.id.in_(seat_ids))
            .order_by(Seat.id.asc())
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_seats_by_event(self, event_id: uuid.UUID) -> Sequence[Seat]:
        """Returns all seats for an event ordered by section, row, and number."""
        stmt = (
            select(Seat)
            .where(Seat.event_id == event_id)
            .order_by(Seat.section.asc(), Seat.row.asc(), Seat.number.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_seats_by_event(self, event_id: uuid.UUID) -> int:
        """Counts total seats allocated for an event."""
        stmt = select(func.count(Seat.id)).where(Seat.event_id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def bulk_create_seats(self, seats: list[Seat]) -> None:
        """Batch inserts seat inventory."""
        self.session.add_all(seats)
        await self.session.flush()

    async def get_seat_by_id(self, seat_id: uuid.UUID) -> Seat | None:
        """Retrieves an individual seat by primary key."""
        stmt = select(Seat).where(Seat.id == seat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
