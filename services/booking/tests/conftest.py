# ruff: noqa: E402
"""Shared pytest fixtures for Booking service tests."""

import sys
import uuid
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

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from redis.asyncio.client import Redis

from app.clients.events_client import EventsClient
from app.config import config
from app.main import create_app
from app.repositories.booking_repository import BookingRepository
from app.repositories.hold_repository import HoldRepository
from app.repositories.seat_repository import SeatRepository
from app.services.hold_service import HoldService
from app.services.inventory_service import InventoryService
from ticketrush_common.security import create_access_token


@pytest.fixture
def mock_seat_repo() -> AsyncMock:
    return AsyncMock(spec=SeatRepository)


@pytest.fixture
def mock_hold_repo() -> AsyncMock:
    return AsyncMock(spec=HoldRepository)


@pytest.fixture
def mock_booking_repo() -> AsyncMock:
    return AsyncMock(spec=BookingRepository)


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    client = AsyncMock(spec=Redis)
    # Default lua eval return: success [1, "OK"]
    client.eval = AsyncMock(return_value=[1, "OK"])
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_events_client() -> AsyncMock:
    client = AsyncMock(spec=EventsClient)
    client.verify_event_on_sale = AsyncMock(
        return_value={"id": str(uuid.uuid4()), "status": "on_sale"}
    )
    return client


@pytest.fixture
def hold_service(
    mock_hold_repo: AsyncMock,
    mock_seat_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    mock_events_client: AsyncMock,
) -> HoldService:
    return HoldService(
        hold_repo=mock_hold_repo,
        seat_repo=mock_seat_repo,
        redis_client=mock_redis_client,
        events_client=mock_events_client,
    )


@pytest.fixture
def inventory_service(mock_seat_repo: AsyncMock) -> InventoryService:
    return InventoryService(seat_repo=mock_seat_repo)


@pytest.fixture
def test_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def test_admin_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_auth_headers(test_user_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(
        user_id=str(test_user_id),
        email="attendee@example.com",
        role="user",
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expires_delta=timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token(
        user_id=str(test_admin_id),
        email="admin@ticketrush.internal",
        role="admin",
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expires_delta=timedelta(minutes=15),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def app_client(
    mock_seat_repo: AsyncMock,
    mock_hold_repo: AsyncMock,
    mock_redis_client: AsyncMock,
    mock_events_client: AsyncMock,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    from app.api.deps import (
        get_events_client,
        get_hold_repository,
        get_redis_client,
        get_seat_repository,
    )

    app = create_app()
    app.dependency_overrides[get_seat_repository] = lambda: mock_seat_repo
    app.dependency_overrides[get_hold_repository] = lambda: mock_hold_repo
    app.dependency_overrides[get_redis_client] = lambda: mock_redis_client
    app.dependency_overrides[get_events_client] = lambda: mock_events_client
    app.state.redis_client = mock_redis_client

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
