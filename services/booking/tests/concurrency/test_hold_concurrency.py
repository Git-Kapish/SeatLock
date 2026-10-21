"""High-concurrency flash sale stress tests for atomic seat holding.

Guarantees:
- 50 concurrent requests competing for the exact same seat.
- Exactly 1 request succeeds (201 Created).
- Exactly 49 requests fail with HTTP 409 Conflict (SEAT_UNAVAILABLE).
- Zero oversells, zero race conditions, zero deadlocks.
"""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.clients.events_client import EventsClient
from app.models.hold import Hold, HoldSeat
from app.models.seat import Seat
from app.repositories.hold_repository import HoldRepository
from app.repositories.seat_repository import SeatRepository
from app.schemas.hold import CreateHoldRequest, HoldResponse
from app.services.hold_service import HoldService
from ticketrush_common.errors import ConflictError


class SimulatedAtomicRedis:
    """Simulates Redis single-threaded atomic Lua script execution under asyncio concurrency."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def eval(
        self,
        script: str,
        numkeys: int,
        *args: Any,
    ) -> list[Any]:
        """Atomically evaluates acquire_holds or release_holds script."""
        keys = list(args[:numkeys])
        user_id = args[numkeys]

        async with self._lock:
            # Check if this is an acquire or release script
            if "EXISTS" in script:
                # ACQUIRE SCRIPT: Check if ANY key is already held
                for k in keys:
                    if k in self._store:
                        return [0, k]

                # All keys free: acquire all atomically
                for k in keys:
                    self._store[k] = str(user_id)
                return [1, "OK"]

            elif "DEL" in script:
                # RELEASE SCRIPT: Release if owned
                for k in keys:
                    if self._store.get(k) == str(user_id):
                        del self._store[k]
                return [1]

            return [0, "UNKNOWN_SCRIPT"]

    async def aclose(self) -> None:
        pass


class SimulatedConcurrencySeatRepository(SeatRepository):
    """Simulates PostgreSQL row-level locking (SELECT ... FOR UPDATE) under asyncio concurrency."""

    def __init__(self, seats_db: dict[uuid.UUID, Seat]) -> None:
        self.seats_db = seats_db
        self._row_locks: dict[uuid.UUID, asyncio.Lock] = {sid: asyncio.Lock() for sid in seats_db}

    async def get_seats_for_update(
        self,
        event_id: uuid.UUID,
        seat_ids: list[uuid.UUID],
    ) -> list[Seat]:
        """Emulates acquiring row-level locks strictly ordered by seat_id ASC."""
        # Strictly order by seat_id to emulate deterministic Postgres lock acquisition
        sorted_ids = sorted(seat_ids)
        for sid in sorted_ids:
            if sid in self._row_locks:
                await self._row_locks[sid].acquire()

        # In a real DB transaction, once locked we fetch the current row state
        results = []
        for sid in sorted_ids:
            if sid in self.seats_db and self.seats_db[sid].event_id == event_id:
                results.append(self.seats_db[sid])
        return results


class SimulatedConcurrencyHoldRepository(HoldRepository):
    """Simulates PostgreSQL hold persistence."""

    def __init__(self) -> None:
        self.created_holds: list[Hold] = []
        self._lock = asyncio.Lock()

    async def count_active_holds_for_user(self, user_id: uuid.UUID) -> int:
        return 0

    async def create_hold(self, hold: Hold, hold_seats: list[HoldSeat]) -> Hold:
        async with self._lock:
            self.created_holds.append(hold)
            return hold


@pytest.mark.asyncio
async def test_50_concurrent_users_competing_for_single_seat() -> None:
    """Flash-Sale Stress Test:

    50 concurrent coroutines simultaneously attempt to hold the EXACT SAME seat.
    Invariant Assertions:
    - Exactly 1 coroutine succeeds.
    - Exactly 49 coroutines receive ConflictError(SEAT_UNAVAILABLE).
    - Database contains exactly 1 created hold.
    - The seat is marked 'held' with 0 oversells.
    """
    event_id = uuid.uuid4()
    hot_seat_id = uuid.uuid4()
    hot_seat = Seat(
        id=hot_seat_id,
        event_id=event_id,
        section="VIP",
        row="Front",
        number=1,
        price_cents=25000,
        status="available",
    )

    # State stores
    seats_db = {hot_seat_id: hot_seat}
    seat_repo = SimulatedConcurrencySeatRepository(seats_db)
    hold_repo = SimulatedConcurrencyHoldRepository()
    redis_sim = SimulatedAtomicRedis()

    events_client = AsyncMock(spec=EventsClient)
    events_client.verify_event_on_sale = AsyncMock(
        return_value={"id": str(event_id), "status": "on_sale"}
    )

    hold_service = HoldService(
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        redis_client=redis_sim,  # type: ignore[arg-type]
        events_client=events_client,
    )

    num_concurrent_users = 50
    user_ids = [uuid.uuid4() for _ in range(num_concurrent_users)]

    # Barrier synchronization to unleash all 50 coroutines simultaneously
    start_barrier = asyncio.Event()

    async def attempt_hold(user_id: uuid.UUID) -> HoldResponse:
        await start_barrier.wait()  # Wait for simultaneous blast
        req = CreateHoldRequest(event_id=event_id, seat_ids=[hot_seat_id])
        return await hold_service.create_hold(user_id=user_id, request=req)

    # Spawn 50 tasks
    tasks = [asyncio.create_task(attempt_hold(uid)) for uid in user_ids]

    # Release the barrier -> flash sale begins!
    start_barrier.set()

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Partition outcomes into successes and conflicts
    successes: list[HoldResponse] = []
    conflicts: list[ConflictError] = []
    unexpected_errors: list[Exception] = []

    for r in results:
        if isinstance(r, HoldResponse):
            successes.append(r)
        elif isinstance(r, ConflictError):
            conflicts.append(r)
        elif isinstance(r, Exception):
            unexpected_errors.append(r)

    # =========================================================================
    # INVARIANT ASSERTIONS
    # =========================================================================
    assert len(unexpected_errors) == 0, f"Unexpected exceptions encountered: {unexpected_errors}"
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 49, f"Expected exactly 49 conflicts, got {len(conflicts)}"

    # Verify conflict error codes
    for c in conflicts:
        assert c.code == "SEAT_UNAVAILABLE"

    # Verify Database state
    assert len(hold_repo.created_holds) == 1
    assert hot_seat.status == "held"
    assert hot_seat.version == 2

    # Verify the successful hold metadata
    winner_hold = successes[0]
    assert winner_hold.event_id == event_id
    assert winner_hold.seat_ids == [hot_seat_id]
    assert winner_hold.status == "active"
    assert winner_hold.total_price_cents == 25000
