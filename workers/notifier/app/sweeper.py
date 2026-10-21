"""Background sweeper to reconcile expired holds and release seat inventory."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

from redis.asyncio.client import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import config
from app.db import async_session_factory
from app.models import Hold
from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.worker.sweeper")


class HoldSweeper:
    """Reconciles expired seat holds in PostgreSQL and clears active Redis locks."""

    def __init__(
        self,
        redis_client: Redis,
        interval_seconds: int | None = None,
    ) -> None:
        self.redis_client = redis_client
        self.interval_seconds = interval_seconds or config.sweeper_interval_seconds

    async def sweep_once(
        self,
        session: AsyncSession,
        current_time: datetime | None = None,
    ) -> int:
        """Finds and expires overdue holds in a single database transaction."""
        now = current_time or datetime.now(UTC)

        stmt = (
            select(Hold)
            .where(
                Hold.status == "active",
                Hold.expires_at <= now,
            )
            .options(selectinload(Hold.seats))
        )
        result = await session.execute(stmt)
        expired_holds = list(result.scalars().all())

        if not expired_holds:
            return 0

        released_seat_count = 0
        for hold in expired_holds:
            hold.status = "expired"

            for seat in hold.seats:
                if seat.status == "held":
                    seat.status = "available"
                    seat.version = (seat.version or 1) + 1
                    released_seat_count += 1

                # Clear Redis lock key
                redis_key = f"hold:{hold.event_id}:{seat.id}"
                await self.redis_client.delete(redis_key)

        await session.commit()

        logger.info(
            "hold_sweeper_reconciliation_complete",
            expired_holds_count=len(expired_holds),
            released_seats_count=released_seat_count,
        )
        return len(expired_holds)

    async def run(self, stop_event: asyncio.Event) -> None:
        """Periodic background loop running until stop_event is signaled."""
        logger.info(
            "hold_sweeper_started",
            interval_seconds=self.interval_seconds,
        )

        while not stop_event.is_set():
            try:
                async with async_session_factory() as session:
                    await self.sweep_once(session)
            except Exception as exc:
                logger.error("hold_sweeper_iteration_failed", error=str(exc))

            # Sleep with early exit if stop_event is set
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.interval_seconds,
                )

        logger.info("hold_sweeper_stopped")
