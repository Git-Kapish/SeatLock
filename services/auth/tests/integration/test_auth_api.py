"""Integration tests for Auth service HTTP API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_auth_service
from app.main import app
from app.schemas.auth import TokenResponse, UserResponse
from app.services.auth_service import AuthService
from ticketrush_common.security import create_access_token

SECRET = "test-secret-key-that-is-at-least-32-chars-long"


@pytest.fixture
def mock_service():
    return AsyncMock(spec=AuthService)


@pytest.mark.asyncio
async def test_health_live_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_register_endpoint_success(mock_service):
    user_id = uuid.uuid4()
    mock_service.register.return_value = UserResponse(
        id=user_id,
        email="newuser@example.com",
        role="user",
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_auth_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"email": "newuser@example.com", "password": "Password123!", "role": "user"}
            response = await client.post("/api/v1/auth/register", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["role"] == "user"
            assert "X-Request-ID" in response.headers
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_endpoint_success(mock_service):
    mock_service.login.return_value = TokenResponse(
        access_token="mocked-jwt-token",
        refresh_token="mocked-refresh-token",
        token_type="Bearer",
        expires_in=900,
    )
    app.dependency_overrides[get_auth_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {"email": "user@example.com", "password": "Password123!"}
            response = await client.post("/api/v1/auth/login", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "mocked-jwt-token"
            assert data["refresh_token"] == "mocked-refresh-token"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_endpoint_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTH_CREDENTIALS_MISSING"


@pytest.mark.asyncio
async def test_me_endpoint_with_valid_token(mock_service):
    user_id = uuid.uuid4()
    mock_service.get_user_profile.return_value = UserResponse(
        id=user_id,
        email="valid@example.com",
        role="user",
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_auth_service] = lambda: mock_service

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            from app.config import config

            token_valid = create_access_token(
                user_id=str(user_id),
                email="valid@example.com",
                role="user",
                secret_key=config.jwt_secret_key,
            )
            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_valid}"}
            )
            assert response.status_code == 200
            assert response.json()["email"] == "valid@example.com"
    finally:
        app.dependency_overrides.clear()
