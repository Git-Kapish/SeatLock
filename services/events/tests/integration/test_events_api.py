"""Integration tests for Events service HTTP API endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_event_service
from app.config import config
from app.main import app
from app.schemas.event import EventResponse
from app.services.event_service import EventService
from ticketrush_common.pagination import PaginatedResponse
from ticketrush_common.security import create_access_token


@pytest.fixture
def mock_event_service():
    return AsyncMock(spec=EventService)


def sample_event_response(event_id: uuid.UUID | None = None) -> EventResponse:
    return EventResponse(
        id=event_id or uuid.uuid4(),
        title="Rock Festival 2026",
        description="Epic outdoor rock and metal music festival.",
        venue="O2 Arena",
        city="London",
        category="Music",
        starts_at=datetime.now(UTC) + timedelta(days=60),
        status="on_sale",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_health_live():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/live")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_public_list_events(mock_event_service):
    ev = sample_event_response()
    mock_event_service.list_events.return_value = PaginatedResponse(
        items=[ev],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
    )
    app.dependency_overrides[get_event_service] = lambda: mock_event_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/v1/events?city=London")
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["title"] == "Rock Festival 2026"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_get_event(mock_event_service):
    ev_id = uuid.uuid4()
    ev = sample_event_response(event_id=ev_id)
    mock_event_service.get_event.return_value = ev
    app.dependency_overrides[get_event_service] = lambda: mock_event_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get(f"/api/v1/events/{ev_id}")
            assert res.status_code == 200
            assert res.json()["title"] == "Rock Festival 2026"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_create_event_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "title": "New Event",
            "description": "Long enough description",
            "venue": "Hall",
            "city": "Paris",
            "category": "Concert",
            "starts_at": datetime.now(UTC).isoformat(),
        }
        res = await client.post("/api/v1/events", json=payload)
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_create_event_forbidden_with_user_role():
    token = create_access_token(
        user_id=str(uuid.uuid4()),
        email="user@test.com",
        role="user",
        secret_key=config.jwt_secret_key,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "title": "New Event",
            "description": "Long enough description",
            "venue": "Hall",
            "city": "Paris",
            "category": "Concert",
            "starts_at": datetime.now(UTC).isoformat(),
        }
        res = await client.post(
            "/api/v1/events",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_admin_create_event_success(mock_event_service):
    token = create_access_token(
        user_id=str(uuid.uuid4()),
        email="admin@test.com",
        role="admin",
        secret_key=config.jwt_secret_key,
    )
    ev = sample_event_response()
    mock_event_service.create_event.return_value = ev
    app.dependency_overrides[get_event_service] = lambda: mock_event_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "title": "Rock Festival 2026",
                "description": "Epic outdoor rock and metal music festival.",
                "venue": "O2 Arena",
                "city": "London",
                "category": "Music",
                "starts_at": datetime.now(UTC).isoformat(),
                "status": "draft",
            }
            res = await client.post(
                "/api/v1/events",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 201
            assert res.json()["title"] == "Rock Festival 2026"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_internal_validate_event_requires_secret():
    ev_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/internal/events/{ev_id}")
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INTERNAL_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_internal_validate_event_success(mock_event_service):
    ev_id = uuid.uuid4()
    ev = sample_event_response(event_id=ev_id)
    mock_event_service.validate_event_for_booking.return_value = ev
    app.dependency_overrides[get_event_service] = lambda: mock_event_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"X-Internal-Secret": config.internal_service_secret}
            res = await client.get(f"/api/v1/internal/events/{ev_id}", headers=headers)
            assert res.status_code == 200
            assert res.json()["status"] == "on_sale"
    finally:
        app.dependency_overrides.clear()
