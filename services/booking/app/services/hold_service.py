"""Hold service managing atomic Redis locks and PostgreSQL row locking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio.client import Redis

from app.clients.events_client import EventsClient
from app.config import config
from app.models.hold import Hold, HoldSeat
from app.redis_scripts import ACQUIRE_HOLDS_LUA, RELEASE_HOLDS_LUA
from app.repositories.hold_repository import HoldRepository
from app.repositories.seat_repository import SeatRepository
from app.schemas.hold import CreateHoldRequest, HoldResponse
from ticketrush_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError


class HoldService:
    """Orchestrates atomic seat holds using Redis Lua scripts and PostgreSQL FOR UPDATE row locks."""

    def __init__(
        self,
        hold_repo: HoldRepository,
        seat_repo: SeatRepository,
        redis_client: Redis,
        events_client: EventsClient,
    ) -> None:
        self.hold_repo = hold_repo
        self.seat_repo = seat_repo
        self.redis_client = redis_client
        self.events_client = events_client

    async def create_hold(
        self,
        user_id: uuid.UUID,
        request: CreateHoldRequest,
    ) -> HoldResponse:
        """Atomically holds requested seats for the user.

        Concurrency & Invariant Guarantees:
        1. Request limit: between 1 and 6 seats.
        2. User limit: max 3 concurrent active holds per user.
        3. Event status: must be confirmed 'on_sale' via Events service.
        4. Redis step: all-or-nothing atomic Lua script (SET NX EX).
        5. PostgreSQL step: SELECT ... FOR UPDATE ordered by seat_id ASC (deadlock prevention).
        6. Seat status verification: must all be currently 'available'.
        7. On any database failure: Redis keys are rolled back immediately.
        """
        # 1. Validate request bounds
        seat_ids = request.seat_ids
        if not seat_ids:
            raise ValidationError(
                message="At least one seat must be selected",
                code="EMPTY_SEAT_SELECTION",
            )
        if len(seat_ids) > config.max_seats_per_hold:
            raise ValidationError(
                message=f"Cannot hold more than {config.max_seats_per_hold} seats in a single request",
                code="HOLD_LIMIT_EXCEEDED",
                details={"max_allowed": config.max_seats_per_hold, "requested": len(seat_ids)},
            )

        # De-duplicate requested seat IDs
        unique_seat_ids = list(dict.fromkeys(seat_ids))
        if len(unique_seat_ids) != len(seat_ids):
            raise ValidationError(
                message="Duplicate seat IDs in hold request",
                code="DUPLICATE_SEAT_SELECTION",
            )

        # 2. Confirm event is on sale (cached in Redis to handle high concurrency)
        event_cache_key = f"cache:event_status:{request.event_id}"
        cached_status = await self.redis_client.get(event_cache_key)
        if cached_status != "on_sale":
            event_data = await self.events_client.verify_event_on_sale(request.event_id)
            if event_data.get("status") == "on_sale":
                await self.redis_client.set(event_cache_key, "on_sale", ex=10)

        # 3. Redis atomic all-or-nothing hold
        redis_keys = [f"hold:{request.event_id}:{s_id}" for s_id in seat_ids]
        lua_res = await self.redis_client.eval(
            ACQUIRE_HOLDS_LUA,
            len(redis_keys),
            *redis_keys,
            str(user_id),
            str(config.hold_ttl_seconds),
        )

        success = bool(lua_res[0]) if isinstance(lua_res, list | tuple) else False
        if not success:
            conflicting_key = (
                lua_res[1] if isinstance(lua_res, list | tuple) and len(lua_res) > 1 else None
            )
            raise ConflictError(
                message="One or more selected seats are no longer available",
                code="SEAT_UNAVAILABLE",
                details={"conflicting_key": conflicting_key},
            )

        # 4. PostgreSQL row-level locking & database transaction
        try:
            # Enforce max active holds per user (Rule B9) only for the winning hold attempt
            active_holds_count = await self.hold_repo.count_active_holds_for_user(user_id)
            if active_holds_count >= config.max_active_holds_per_user:
                await self.redis_client.eval(
                    RELEASE_HOLDS_LUA,
                    len(redis_keys),
                    *redis_keys,
                    str(user_id),
                )
                raise ConflictError(
                    message=f"User has reached the limit of {config.max_active_holds_per_user} active holds",
                    code="MAX_ACTIVE_HOLDS_REACHED",
                    details={
                        "active_holds": active_holds_count,
                        "limit": config.max_active_holds_per_user,
                    },
                )

            # Deterministic ID sorting eliminates deadlocks under high concurrency
            locked_seats = await self.seat_repo.get_seats_for_update(request.event_id, seat_ids)

            # Verify all requested seats exist for this event
            if len(locked_seats) != len(seat_ids):
                # Rollback Redis hold keys
                await self.redis_client.eval(
                    RELEASE_HOLDS_LUA,
                    len(redis_keys),
                    *redis_keys,
                    str(user_id),
                )
                raise NotFoundError(
                    message="One or more requested seats do not exist for this event",
                    code="SEAT_NOT_FOUND",
                )

            # Verify all locked seats are currently available
            unavailable_seats = [s.id for s in locked_seats if s.status != "available"]
            if unavailable_seats:
                # Rollback Redis hold keys
                await self.redis_client.eval(
                    RELEASE_HOLDS_LUA,
                    len(redis_keys),
                    *redis_keys,
                    str(user_id),
                )
                raise ConflictError(
                    message="One or more selected seats are already held or booked",
                    code="SEAT_UNAVAILABLE",
                    details={"unavailable_seat_ids": [str(sid) for sid in unavailable_seats]},
                )

            # All seats free: compute expiration & prices
            now = datetime.now(UTC)
            expires_at = now + timedelta(seconds=config.hold_ttl_seconds)
            total_price_cents = sum(s.price_cents for s in locked_seats)

            hold_id = uuid.uuid4()
            hold = Hold(
                id=hold_id,
                user_id=user_id,
                event_id=request.event_id,
                status="active",
                expires_at=expires_at,
                created_at=now,
            )
            hold_seats = [HoldSeat(hold_id=hold_id, seat_id=s.id) for s in locked_seats]

            # Transition seat statuses
            for s in locked_seats:
                s.status = "held"
                s.version = (s.version or 1) + 1

            await self.hold_repo.create_hold(hold, hold_seats)

            return HoldResponse(
                id=hold.id,
                user_id=hold.user_id,
                event_id=hold.event_id,
                status=hold.status,
                expires_at=hold.expires_at,
                created_at=hold.created_at,
                seat_ids=[s.id for s in locked_seats],
                total_price_cents=total_price_cents,
            )

        except (ConflictError, NotFoundError, ValidationError):
            raise
        except Exception:
            # Revert Redis locks on any unexpected failure
            await self.redis_client.eval(
                RELEASE_HOLDS_LUA,
                len(redis_keys),
                *redis_keys,
                str(user_id),
            )
            raise

    async def get_hold(self, hold_id: uuid.UUID, user_id: uuid.UUID) -> HoldResponse:
        """Retrieves details of an existing hold, verifying caller ownership."""
        hold = await self.hold_repo.get_hold_by_id(hold_id)
        if not hold:
            raise NotFoundError(
                message=f"Hold {hold_id} not found",
                code="HOLD_NOT_FOUND",
            )
        if hold.user_id != user_id:
            raise ForbiddenError(
                message="Not authorized to view this hold",
                code="HOLD_ACCESS_DENIED",
            )

        seat_ids = [s.id for s in hold.seats]
        total_cents = sum(s.price_cents for s in hold.seats)

        return HoldResponse(
            id=hold.id,
            user_id=hold.user_id,
            event_id=hold.event_id,
            status=hold.status,
            expires_at=hold.expires_at,
            created_at=hold.created_at,
            seat_ids=seat_ids,
            total_price_cents=total_cents,
        )

    async def release_hold(
        self,
        hold_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
    ) -> None:
        """Releases an active hold, returning held seats to available in DB and Redis."""
        hold = await self.hold_repo.get_hold_by_id(hold_id)
        if not hold:
            raise NotFoundError(
                message=f"Hold {hold_id} not found",
                code="HOLD_NOT_FOUND",
            )
        if not is_admin and hold.user_id != user_id:
            raise ForbiddenError(
                message="Not authorized to release this hold",
                code="HOLD_ACCESS_DENIED",
            )
        if hold.status != "active":
            raise ConflictError(
                message=f"Hold is not active (status: '{hold.status}')",
                code="HOLD_NOT_ACTIVE",
            )

        seat_ids = [s.id for s in hold.seats]
        if seat_ids:
            locked_seats = await self.seat_repo.get_seats_for_update(hold.event_id, seat_ids)
            for s in locked_seats:
                if s.status == "held":
                    s.status = "available"
                    s.version = (s.version or 1) + 1

            redis_keys = [f"hold:{hold.event_id}:{s_id}" for s_id in seat_ids]
            await self.redis_client.eval(
                RELEASE_HOLDS_LUA,
                len(redis_keys),
                *redis_keys,
                str(hold.user_id),
            )

        hold.status = "released"
