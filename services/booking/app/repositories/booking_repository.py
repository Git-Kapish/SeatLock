"""Repository for Booking entities and seat allocations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingSeat


class BookingRepository:
    """Encapsulates booking creation, lookup, and updates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_booking(
        self,
        booking: Booking,
        booking_seats: list[BookingSeat],
    ) -> Booking:
        """Persists a new booking and its associated seats."""
        self.session.add(booking)
        await self.session.flush()
        self.session.add_all(booking_seats)
        await self.session.flush()
        return booking

    async def get_booking_by_id(self, booking_id: uuid.UUID) -> Booking | None:
        """Finds booking by primary key including preloaded seats."""
        stmt = select(Booking).where(Booking.id == booking_id).options(selectinload(Booking.seats))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_user_bookings(self, user_id: uuid.UUID) -> Sequence[Booking]:
        """Lists all bookings belonging to a user."""
        stmt = (
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
            .options(selectinload(Booking.seats))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
