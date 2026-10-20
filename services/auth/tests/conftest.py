# ruff: noqa: E402
"""Shared pytest fixtures for Auth service tests."""

import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
else:
    sys.path.remove(str(SERVICE_ROOT))
    sys.path.insert(0, str(SERVICE_ROOT))

# Unload any previously imported 'app' modules from other services in monorepo
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import AuthConfig
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from ticketrush_common.redis import RedisManager


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


@pytest.fixture
def mock_redis_manager() -> MagicMock:
    manager = MagicMock(spec=RedisManager)
    manager.check_rate_limit = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock(return_value=True)
    mock_client.ping = AsyncMock(return_value=True)
    manager.get_client = MagicMock(return_value=mock_client)
    manager.close = AsyncMock()
    return manager


@pytest.fixture
def test_config() -> AuthConfig:
    return AuthConfig(
        jwt_secret_key="test-secret-key-that-is-at-least-32-chars-long",
        jwt_algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        login_rate_limit_max=5,
        login_rate_limit_window_seconds=60,
    )


@pytest.fixture
def auth_service(
    mock_user_repo: AsyncMock, mock_redis_manager: MagicMock, test_config: AuthConfig
) -> AuthService:
    return AuthService(
        user_repo=mock_user_repo,
        redis_manager=mock_redis_manager,
        config=test_config,
    )
