"""Async Redis client management and distributed rate limiting."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.client import Redis

from ticketrush_common.errors import RateLimitError
from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.redis")

# Atomic token bucket / sliding window rate limiter script in Lua
# Keys: [rate_limit_key]
# ARGV: [max_requests, window_seconds]
RATE_LIMIT_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window)
end

if current > limit then
    local ttl = redis.call('TTL', key)
    return {0, ttl}
else
    return {1, limit - current}
end
"""


class RedisManager:
    """Manages Redis connection pooling and common caching/locking utilities."""

    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._pool: aioredis.ConnectionPool | None = None
        self._rate_limit_script: Any = None

    def get_client(self) -> Redis:
        """Returns an async Redis client backed by the connection pool."""
        if self._pool is None:
            self._pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=50,
                decode_responses=True,
            )
        client: Redis = Redis(connection_pool=self._pool)
        if self._rate_limit_script is None:
            self._rate_limit_script = client.register_script(RATE_LIMIT_LUA)
        return client

    async def close(self) -> None:
        """Closes the connection pool gracefully."""
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            logger.info("redis_connection_pool_closed")

    async def check_rate_limit(
        self,
        key_identifier: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        """Enforces a rate limit. Raises RateLimitError with Retry-After if exceeded."""
        _ = self.get_client()
        rate_key = f"ratelimit:{key_identifier}"
        try:
            allowed, remaining_or_ttl = await self._rate_limit_script(
                keys=[rate_key],
                args=[max_requests, window_seconds],
            )
            if allowed == 0:
                retry_after = max(1, int(remaining_or_ttl))
                logger.warning(
                    "rate_limit_exceeded",
                    key=key_identifier,
                    retry_after=retry_after,
                )
                raise RateLimitError(
                    message=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s.",
                    retry_after_seconds=retry_after,
                )
        except aioredis.RedisError as exc:
            # If Redis fails, log warning and fail open for availability
            logger.error("redis_rate_limit_check_error_failing_open", error=str(exc))


@asynccontextmanager
async def lifespan_redis(redis_url: str) -> AsyncGenerator[RedisManager, None]:
    """FastAPI lifespan helper for initializing and tearing down Redis."""
    manager = RedisManager(redis_url)
    try:
        yield manager
    finally:
        await manager.close()
