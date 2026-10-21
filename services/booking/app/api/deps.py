"""FastAPI dependencies for Booking service."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import Depends, Request
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.events_client import EventsClient
from app.config import config
from app.db import get_db_session
from app.repositories.booking_repository import BookingRepository
from app.repositories.hold_repository import HoldRepository
from app.repositories.seat_repository import SeatRepository
from app.services.hold_service import HoldService
from app.services.inventory_service import InventoryService
from ticketrush_common.security import (
    get_current_user_claims_factory,
    require_role,
)


def get_seat_repository(session: AsyncSession = Depends(get_db_session)) -> SeatRepository:
    """Yields a SeatRepository bound to the current request session."""
    return SeatRepository(session)


def get_hold_repository(session: AsyncSession = Depends(get_db_session)) -> HoldRepository:
    """Yields a HoldRepository bound to the current request session."""
    return HoldRepository(session)


def get_booking_repository(session: AsyncSession = Depends(get_db_session)) -> BookingRepository:
    """Yields a BookingRepository bound to the current request session."""
    return BookingRepository(session)


def get_redis_client(request: Request) -> Redis:
    """Retrieves async Redis client from app state."""
    client = getattr(request.app.state, "redis_client", None)
    if client is None:
        client = aioredis.from_url(config.redis_url, decode_responses=True)
        request.app.state.redis_client = client
    return client


def get_events_client() -> EventsClient:
    """Yields EventsClient configured with service URL and shared secret."""
    return EventsClient(
        base_url=config.events_service_url,
        internal_secret=config.internal_service_secret,
    )


def get_hold_service(
    hold_repo: HoldRepository = Depends(get_hold_repository),
    seat_repo: SeatRepository = Depends(get_seat_repository),
    redis_client: Redis = Depends(get_redis_client),
    events_client: EventsClient = Depends(get_events_client),
) -> HoldService:
    """Yields HoldService configured with repos, redis, and events client."""
    return HoldService(
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        redis_client=redis_client,
        events_client=events_client,
    )


def get_inventory_service(
    seat_repo: SeatRepository = Depends(get_seat_repository),
) -> InventoryService:
    """Yields InventoryService configured with SeatRepository."""
    return InventoryService(seat_repo=seat_repo)


# Security dependencies
get_current_user = get_current_user_claims_factory(
    secret_key=config.jwt_secret_key,
    algorithm=config.jwt_algorithm,
)

require_admin = require_role("admin", user_dependency=get_current_user)
