"""FastAPI dependencies for Booking service."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends, Request, Response
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.events_client import EventsClient
from app.config import config
from app.db import get_db_session
from app.repositories.booking_repository import BookingRepository
from app.repositories.hold_repository import HoldRepository
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.seat_repository import SeatRepository
from app.services.booking_service import BookingService
from app.services.hold_service import HoldService
from app.services.idempotency_service import IdempotencyService
from app.services.inventory_service import InventoryService
from app.services.payment_service import PaymentService
from ticketrush_common.redis import RedisManager
from ticketrush_common.security import (
    UserClaims,
    get_current_user_claims_factory,
    require_role,
)
from ticketrush_common.sqs import SQSClient


def get_seat_repository(session: AsyncSession = Depends(get_db_session)) -> SeatRepository:
    """Yields a SeatRepository bound to the current request session."""
    return SeatRepository(session)


def get_hold_repository(session: AsyncSession = Depends(get_db_session)) -> HoldRepository:
    """Yields a HoldRepository bound to the current request session."""
    return HoldRepository(session)


def get_booking_repository(session: AsyncSession = Depends(get_db_session)) -> BookingRepository:
    """Yields a BookingRepository bound to the current request session."""
    return BookingRepository(session)


def get_payment_repository(session: AsyncSession = Depends(get_db_session)) -> PaymentRepository:
    """Yields a PaymentRepository bound to the current request session."""
    return PaymentRepository(session)


def get_idempotency_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IdempotencyRepository:
    """Yields an IdempotencyRepository bound to the current request session."""
    return IdempotencyRepository(session)


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


def get_sqs_client() -> SQSClient:
    """Yields an SQSClient configured with AWS/LocalStack credentials."""
    return SQSClient(
        region_name=config.aws_region,
        endpoint_url=config.sqs_endpoint_url,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
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


def get_idempotency_service(
    idempotency_repo: IdempotencyRepository = Depends(get_idempotency_repository),
) -> IdempotencyService:
    """Yields IdempotencyService configured with IdempotencyRepository."""
    return IdempotencyService(idempotency_repo=idempotency_repo)


def get_payment_service(
    payment_repo: PaymentRepository = Depends(get_payment_repository),
    booking_repo: BookingRepository = Depends(get_booking_repository),
    hold_repo: HoldRepository = Depends(get_hold_repository),
    seat_repo: SeatRepository = Depends(get_seat_repository),
    redis_client: Redis = Depends(get_redis_client),
    sqs_client: SQSClient = Depends(get_sqs_client),
) -> PaymentService:
    """Yields PaymentService configured with repos, redis, and sqs."""
    return PaymentService(
        payment_repo=payment_repo,
        booking_repo=booking_repo,
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        redis_client=redis_client,
        sqs_client=sqs_client,
    )


def get_booking_service(
    booking_repo: BookingRepository = Depends(get_booking_repository),
    hold_repo: HoldRepository = Depends(get_hold_repository),
    seat_repo: SeatRepository = Depends(get_seat_repository),
    payment_service: PaymentService = Depends(get_payment_service),
) -> BookingService:
    """Yields BookingService configured with repos and payment service."""
    return BookingService(
        booking_repo=booking_repo,
        hold_repo=hold_repo,
        seat_repo=seat_repo,
        payment_service=payment_service,
    )


# Security dependencies
get_current_user = get_current_user_claims_factory(
    secret_key=config.jwt_secret_key,
    algorithm=config.jwt_algorithm,
)

require_admin = require_role("admin", user_dependency=get_current_user)


def check_rate_limit_dependency(max_requests: int, window_seconds: int = 60) -> Any:
    """FastAPI dependency enforcing Redis token bucket rate limiting per authenticated user."""

    async def rate_limiter(
        request: Request,
        response: Response,
        current_user: UserClaims = Depends(get_current_user),
    ) -> None:
        redis_manager: RedisManager | None = getattr(request.app.state, "redis_manager", None)
        if redis_manager is None:
            redis_manager = RedisManager(config.redis_url)
            request.app.state.redis_manager = redis_manager

        rate_key = f"{request.url.path}:{current_user.user_id}"
        remaining, _ = await redis_manager.check_rate_limit(
            key_identifier=rate_key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    return rate_limiter


rate_limit_holds = check_rate_limit_dependency(max_requests=10, window_seconds=60)
rate_limit_bookings = check_rate_limit_dependency(max_requests=5, window_seconds=60)
