# ruff: noqa: E402
"""Shared pytest fixtures for Events service tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from redis.asyncio.client import Redis

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

from app.repositories.event_repository import EventRepository
from app.services.event_service import EventService


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock(spec=EventRepository)


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    client = AsyncMock(spec=Redis)
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.scan = AsyncMock(return_value=(0, []))
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def event_service(mock_event_repo: AsyncMock, mock_redis_client: AsyncMock) -> EventService:
    return EventService(event_repo=mock_event_repo, redis_client=mock_redis_client)
