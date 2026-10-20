"""FastAPI dependencies for Auth service."""

from __future__ import annotations

from typing import cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from ticketrush_common.redis import RedisManager
from ticketrush_common.security import (
    get_current_user_claims_factory,
    require_role,
)


def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    """Yields a UserRepository instance bound to the request's DB session."""
    return UserRepository(session)


def get_redis_manager(request: Request) -> RedisManager:
    """Retrieves the application-wide RedisManager from app state."""
    return cast("RedisManager", request.app.state.redis_manager)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    redis_mgr: RedisManager = Depends(get_redis_manager),
) -> AuthService:
    """Provides AuthService configured with repository and redis manager."""
    return AuthService(user_repo=user_repo, redis_manager=redis_mgr, config=config)


# Dependency to extract and verify JWT claims from Authorization Bearer header
get_current_user = get_current_user_claims_factory(
    secret_key=config.jwt_secret_key,
    algorithm=config.jwt_algorithm,
)

# Admin role guard
require_admin = require_role("admin", user_dependency=get_current_user)
