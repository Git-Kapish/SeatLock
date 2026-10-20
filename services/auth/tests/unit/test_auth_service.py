"""Unit tests for AuthService business logic with mocked dependencies."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest
from app.services.auth_service import AuthService
from ticketrush_common.errors import AuthenticationError, ConflictError, NotFoundError
from ticketrush_common.security import hash_password


@pytest.mark.asyncio
async def test_register_success(auth_service: AuthService, mock_user_repo: AsyncMock):
    mock_user_repo.get_by_email.return_value = None
    created_user = User(
        id=uuid.uuid4(),
        email="attendee@example.com",
        password_hash="hashed",
        role="user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_user_repo.create_user.return_value = created_user

    req = RegisterRequest(email="attendee@example.com", password="SecurePassword123!", role="user")
    res = await auth_service.register(req)

    assert res.email == "attendee@example.com"
    assert res.role == "user"
    mock_user_repo.create_user.assert_called_once()


@pytest.mark.asyncio
async def test_register_duplicate_email(auth_service: AuthService, mock_user_repo: AsyncMock):
    existing_user = User(
        id=uuid.uuid4(),
        email="existing@example.com",
        password_hash="hashed",
        role="user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_user_repo.get_by_email.return_value = existing_user

    req = RegisterRequest(email="existing@example.com", password="SecurePassword123!")
    with pytest.raises(ConflictError) as exc_info:
        await auth_service.register(req)
    assert exc_info.value.code == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService, mock_user_repo: AsyncMock):
    raw_pwd = "MySecretPassword123!"
    hashed = hash_password(raw_pwd)
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        password_hash=hashed,
        role="user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_user_repo.get_by_email.return_value = user
    mock_user_repo.create_refresh_token.return_value = None

    req = LoginRequest(email="user@example.com", password=raw_pwd)
    token_res = await auth_service.login(req, client_ip="127.0.0.1")

    assert token_res.access_token is not None
    assert token_res.refresh_token is not None
    assert token_res.token_type == "Bearer"
    assert token_res.expires_in == 15 * 60


@pytest.mark.asyncio
async def test_login_invalid_password(auth_service: AuthService, mock_user_repo: AsyncMock):
    hashed = hash_password("CorrectPassword123!")
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        password_hash=hashed,
        role="user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_user_repo.get_by_email.return_value = user

    req = LoginRequest(email="user@example.com", password="WrongPassword!")
    with pytest.raises(AuthenticationError) as exc_info:
        await auth_service.login(req, client_ip="127.0.0.1")
    assert exc_info.value.code == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_refresh_token_rotation_success(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
):
    user_id = uuid.uuid4()
    raw_refresh = "valid-raw-refresh-token"
    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=AuthService._hash_token(raw_refresh),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=None,
        created_at=datetime.now(UTC),
    )
    user = User(
        id=user_id,
        email="user@example.com",
        password_hash="hash",
        role="user",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_user_repo.get_refresh_token.return_value = token_record
    mock_user_repo.get_by_id.return_value = user
    mock_user_repo.create_refresh_token.return_value = None

    req = RefreshTokenRequest(refresh_token=raw_refresh)
    res = await auth_service.refresh_tokens(req)

    assert res.access_token is not None
    assert res.refresh_token is not None
    mock_user_repo.revoke_refresh_token.assert_called_once()
    mock_user_repo.create_refresh_token.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_token_revoked_fails(auth_service: AuthService, mock_user_repo: AsyncMock):
    raw_refresh = "already-revoked-token"
    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=AuthService._hash_token(raw_refresh),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=datetime.now(UTC),  # already revoked
        created_at=datetime.now(UTC),
    )
    mock_user_repo.get_refresh_token.return_value = token_record

    req = RefreshTokenRequest(refresh_token=raw_refresh)
    with pytest.raises(AuthenticationError) as exc_info:
        await auth_service.refresh_tokens(req)
    assert exc_info.value.code == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_refresh_token_expired_fails(auth_service: AuthService, mock_user_repo: AsyncMock):
    raw_refresh = "expired-token"
    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash=AuthService._hash_token(raw_refresh),
        expires_at=datetime.now(UTC) - timedelta(days=1),  # expired
        revoked_at=None,
        created_at=datetime.now(UTC) - timedelta(days=8),
    )
    mock_user_repo.get_refresh_token.return_value = token_record

    req = RefreshTokenRequest(refresh_token=raw_refresh)
    with pytest.raises(AuthenticationError) as exc_info:
        await auth_service.refresh_tokens(req)
    assert exc_info.value.code == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_get_user_profile_not_found(auth_service: AuthService, mock_user_repo: AsyncMock):
    mock_user_repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await auth_service.get_user_profile(uuid.uuid4())
