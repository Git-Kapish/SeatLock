"""Security utilities: Argon2 password hashing, JWT encoding/decoding, and FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from ticketrush_common.errors import AuthenticationError, ForbiddenError

_hasher = PasswordHasher()
_bearer_scheme = HTTPBearer(auto_error=False)


class UserClaims(BaseModel):
    """Parsed and validated JWT access token claims."""

    user_id: str = Field(..., alias="sub")
    email: str
    role: str
    exp: int


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> str:
    """Creates a signed short-lived JWT access token."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=15))
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, secret_key: str, algorithm: str = "HS256") -> UserClaims:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return UserClaims(**payload)
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            message="Token has expired",
            code="TOKEN_EXPIRED",
        ) from exc
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AuthenticationError(
            message="Invalid authentication token",
            code="INVALID_TOKEN",
        ) from exc


def get_current_user_claims_factory(
    secret_key: str, algorithm: str = "HS256"
) -> Callable[..., Awaitable[UserClaims]]:
    """Factory creating a FastAPI dependency to authenticate user claims from Bearer token."""

    async def get_current_user(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> UserClaims:
        if not creds or not creds.credentials:
            raise AuthenticationError(
                message="Missing authentication credentials",
                code="AUTH_CREDENTIALS_MISSING",
            )
        return decode_access_token(creds.credentials, secret_key, algorithm)

    return get_current_user


def require_role(required_role: str, user_dependency: Any) -> Callable[[UserClaims], UserClaims]:
    """Dependency factory checking that the authenticated user possesses the required role."""

    def role_checker(claims: UserClaims = Depends(user_dependency)) -> UserClaims:
        if claims.role != required_role:
            raise ForbiddenError(
                message=f"Access denied: Requires '{required_role}' role",
                code="INSUFFICIENT_PERMISSIONS",
                details={"required_role": required_role, "current_role": claims.role},
            )
        return claims

    return role_checker


def verify_internal_service_token(internal_secret: str) -> Callable[..., Awaitable[None]]:
    """Dependency factory verifying shared secret header for internal service-to-service calls."""

    async def internal_guard(
        x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    ) -> None:
        if not x_internal_secret or x_internal_secret != internal_secret:
            raise ForbiddenError(
                message="Invalid or missing internal service authorization secret",
                code="INTERNAL_ACCESS_DENIED",
            )

    return internal_guard
