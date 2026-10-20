"""FastAPI dependencies for Events service."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import Depends, Request
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import get_db_session
from app.repositories.event_repository import EventRepository
from app.services.event_service import EventService
from ticketrush_common.security import (
    get_current_user_claims_factory,
    require_role,
    verify_internal_service_token,
)


def get_event_repository(session: AsyncSession = Depends(get_db_session)) -> EventRepository:
    """Yields an EventRepository instance bound to the request's DB session."""
    return EventRepository(session)


def get_redis_client(request: Request) -> Redis:
    """Retrieves the async Redis client from app state, initializing if absent."""
    client = getattr(request.app.state, "redis_client", None)
    if client is None:
        client = aioredis.from_url(config.redis_url, decode_responses=True)
        request.app.state.redis_client = client
    return client


def get_event_service(
    event_repo: EventRepository = Depends(get_event_repository),
    redis_client: Redis = Depends(get_redis_client),
) -> EventService:
    """Provides EventService configured with repository and redis client."""
    return EventService(event_repo=event_repo, redis_client=redis_client)


# Security dependencies
get_current_user = get_current_user_claims_factory(
    secret_key=config.jwt_secret_key,
    algorithm=config.jwt_algorithm,
)

require_admin = require_role("admin", user_dependency=get_current_user)

verify_internal_service = verify_internal_service_token(
    internal_secret=config.internal_service_secret,
)
