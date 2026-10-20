from datetime import timedelta

import pytest

from ticketrush_common.errors import AuthenticationError
from ticketrush_common.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-key-32-characters-minimum-for-testing"


def test_password_hashing_and_verification():
    raw = "SuperSecret123!"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_create_and_decode_valid():
    token = create_access_token(
        user_id="user-123",
        email="test@ticketrush.dev",
        role="admin",
        secret_key=SECRET,
        expires_delta=timedelta(minutes=10),
    )
    claims = decode_access_token(token, secret_key=SECRET)
    assert claims.user_id == "user-123"
    assert claims.email == "test@ticketrush.dev"
    assert claims.role == "admin"


def test_jwt_expired_token():
    token = create_access_token(
        user_id="user-123",
        email="test@ticketrush.dev",
        role="user",
        secret_key=SECRET,
        expires_delta=timedelta(seconds=-10),  # expired in past
    )
    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(token, secret_key=SECRET)
    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_jwt_invalid_secret():
    token = create_access_token(
        user_id="user-123",
        email="test@ticketrush.dev",
        role="user",
        secret_key=SECRET,
    )
    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(token, secret_key="wrong-secret-key-that-is-at-least-32-chars-long")
    assert exc_info.value.code == "INVALID_TOKEN"
