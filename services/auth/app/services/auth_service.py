"""Authentication domain service implementing business rules and token rotation."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.config import AuthConfig
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from ticketrush_common.errors import AuthenticationError, ConflictError, NotFoundError
from ticketrush_common.redis import RedisManager
from ticketrush_common.security import create_access_token, hash_password, verify_password

if TYPE_CHECKING:
    from redis.asyncio.client import Redis


class AuthService:
    """Core business logic for user authentication, token issuance, and rotation."""

    def __init__(
        self,
        user_repo: UserRepository,
        redis_manager: RedisManager,
        config: AuthConfig,
    ) -> None:
        self.user_repo = user_repo
        self.redis_manager = redis_manager
        self.config = config

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        """Computes SHA-256 hash of a raw token for safe storage and fast lookup."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    async def register(self, request: RegisterRequest) -> UserResponse:
        """Registers a new user account."""
        existing = await self.user_repo.get_by_email(request.email)
        if existing:
            raise ConflictError(
                message="A user with this email address already exists",
                code="EMAIL_ALREADY_EXISTS",
                details={"email": request.email},
            )

        pwd_hash = hash_password(request.password)
        user = await self.user_repo.create_user(
            email=request.email,
            password_hash=pwd_hash,
            role=request.role,
        )
        return UserResponse.model_validate(user)

    async def login(self, request: LoginRequest, client_ip: str) -> TokenResponse:
        """Authenticates user credentials and issues token pair."""
        # Enforce rate limit per IP + email: 5 attempts / 60 seconds
        rate_key = f"login:{client_ip}:{request.email.lower()}"
        await self.redis_manager.check_rate_limit(
            key_identifier=rate_key,
            max_requests=self.config.login_rate_limit_max,
            window_seconds=self.config.login_rate_limit_window_seconds,
        )

        user = await self.user_repo.get_by_email(request.email)
        if not user or not verify_password(request.password, user.password_hash):
            raise AuthenticationError(
                message="Invalid email or password",
                code="INVALID_CREDENTIALS",
            )

        return await self._issue_tokens(user.id, user.email, user.role)

    async def refresh_tokens(self, request: RefreshTokenRequest) -> TokenResponse:
        """Rotates refresh token and issues a new access token."""
        token_hash = self._hash_token(request.refresh_token)
        redis_client: Redis = self.redis_manager.get_client()

        # Check fast-path Redis revocation cache
        if await redis_client.get(f"revoked_token:{token_hash}"):
            raise AuthenticationError(
                message="Refresh token has been revoked",
                code="TOKEN_REVOKED",
            )

        token_record = await self.user_repo.get_refresh_token(token_hash)
        if not token_record or token_record.revoked_at is not None:
            raise AuthenticationError(
                message="Invalid or revoked refresh token",
                code="TOKEN_REVOKED",
            )

        now = datetime.now(UTC)
        if token_record.expires_at < now:
            raise AuthenticationError(
                message="Refresh token has expired",
                code="TOKEN_EXPIRED",
            )

        # Token rotation: Revoke used token in DB and cache in Redis
        await self.user_repo.revoke_refresh_token(token_hash)
        await redis_client.setex(f"revoked_token:{token_hash}", 86400 * 7, "1")

        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user:
            raise NotFoundError(message="User account no longer exists")

        return await self._issue_tokens(user.id, user.email, user.role)

    async def logout(self, refresh_token_str: str) -> None:
        """Revokes the given refresh token."""
        token_hash = self._hash_token(refresh_token_str)
        await self.user_repo.revoke_refresh_token(token_hash)
        redis_client = self.redis_manager.get_client()
        await redis_client.setex(f"revoked_token:{token_hash}", 86400 * 7, "1")

    async def get_user_profile(self, user_id: uuid.UUID) -> UserResponse:
        """Retrieves user profile by ID."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        return UserResponse.model_validate(user)

    async def _issue_tokens(self, user_id: uuid.UUID, email: str, role: str) -> TokenResponse:
        """Generates access token and persists a new cryptographically random refresh token."""
        access_token_expires = timedelta(minutes=self.config.access_token_expire_minutes)
        access_token = create_access_token(
            user_id=str(user_id),
            email=email,
            role=role,
            secret_key=self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
            expires_delta=access_token_expires,
        )

        raw_refresh_token = secrets.token_urlsafe(48)
        refresh_token_hash = self._hash_token(raw_refresh_token)
        refresh_expires_at = datetime.now(UTC) + timedelta(
            days=self.config.refresh_token_expire_days
        )

        await self.user_repo.create_refresh_token(
            user_id=user_id,
            token_hash=refresh_token_hash,
            expires_at=refresh_expires_at,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="Bearer",
            expires_in=int(access_token_expires.total_seconds()),
        )
