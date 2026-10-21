"""Unit tests for token-bucket rate limiter dependency and response headers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, Response

from app.api.deps import check_rate_limit_dependency
from ticketrush_common.errors import RateLimitError
from ticketrush_common.redis import RedisManager
from ticketrush_common.security import UserClaims


@pytest.mark.asyncio
async def test_rate_limiter_under_limit() -> None:
    """Verifies that requests within limits succeed and set X-RateLimit headers."""
    limiter = check_rate_limit_dependency(max_requests=10, window_seconds=60)

    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/booking/holds"
    mock_redis_manager = MagicMock(spec=RedisManager)
    # Returns (remaining=9, ttl=60)
    mock_redis_manager.check_rate_limit = AsyncMock(return_value=(9, 60))
    request.app.state.redis_manager = mock_redis_manager

    response = Response()
    current_user = UserClaims(
        sub="u1234567-0000-0000-0000-000000000000",
        email="user@example.com",
        role="customer",
        exp=9999999999,
    )

    await limiter(request=request, response=response, current_user=current_user)

    mock_redis_manager.check_rate_limit.assert_awaited_once_with(
        key_identifier="/api/v1/booking/holds:u1234567-0000-0000-0000-000000000000",
        max_requests=10,
        window_seconds=60,
    )
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "9"


@pytest.mark.asyncio
async def test_rate_limiter_exceeded_raises_429() -> None:
    """Verifies that exceeding max_requests raises RateLimitError with Retry-After."""
    limiter = check_rate_limit_dependency(max_requests=5, window_seconds=60)

    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/booking/bookings"
    mock_redis_manager = MagicMock(spec=RedisManager)
    # Simulate RateLimitError raised by RedisManager
    mock_redis_manager.check_rate_limit = AsyncMock(
        side_effect=RateLimitError(
            message="Rate limit exceeded",
            retry_after_seconds=45,
            limit=5,
        )
    )
    request.app.state.redis_manager = mock_redis_manager

    response = Response()
    current_user = UserClaims(
        sub="u1234567-0000-0000-0000-000000000000",
        email="user@example.com",
        role="customer",
        exp=9999999999,
    )

    with pytest.raises(RateLimitError) as exc_info:
        await limiter(request=request, response=response, current_user=current_user)

    err = exc_info.value
    assert err.status_code == 429
    assert err.headers["Retry-After"] == "45"
    assert err.headers["X-RateLimit-Limit"] == "5"
    assert err.headers["X-RateLimit-Remaining"] == "0"
