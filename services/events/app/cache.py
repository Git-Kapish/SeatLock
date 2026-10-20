"""Redis cache-aside helpers for event listings and details."""

from __future__ import annotations

import json
from typing import Any, cast

from redis.asyncio.client import Redis

from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.events.cache")

EVENT_DETAIL_KEY_PREFIX = "cache:event:"
EVENT_LIST_KEY_PREFIX = "cache:events:list:"


class EventCache:
    """Manages event catalog caching in Redis with proactive invalidation."""

    def __init__(self, redis_client: Redis, default_ttl: int = 300) -> None:
        self.client: Redis = redis_client
        self.default_ttl = default_ttl

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        """Retrieves cached event details JSON."""
        key = f"{EVENT_DETAIL_KEY_PREFIX}{event_id}"
        try:
            cached = await self.client.get(key)
            if cached:
                return cast("dict[str, Any]", json.loads(cached))
        except Exception as exc:
            logger.warning("cache_read_error", key=key, error=str(exc))
        return None

    async def set_event(self, event_id: str, data: dict[str, Any]) -> None:
        """Caches event details with default TTL."""
        key = f"{EVENT_DETAIL_KEY_PREFIX}{event_id}"
        try:
            await self.client.setex(key, self.default_ttl, json.dumps(data, default=str))
        except Exception as exc:
            logger.warning("cache_write_error", key=key, error=str(exc))

    async def invalidate_event(self, event_id: str) -> None:
        """Invalidates both the specific event cache and catalog list caches."""
        try:
            detail_key = f"{EVENT_DETAIL_KEY_PREFIX}{event_id}"
            await self.client.delete(detail_key)

            # Invalidate all listing caches using SCAN
            cursor = 0
            while True:
                cursor, keys = await self.client.scan(
                    cursor=cursor, match=f"{EVENT_LIST_KEY_PREFIX}*", count=100
                )
                if keys:
                    await self.client.delete(*keys)
                if cursor == 0:
                    break
            logger.info("event_cache_invalidated", event_id=event_id)
        except Exception as exc:
            logger.warning("cache_invalidation_error", event_id=event_id, error=str(exc))

    async def get_listing(self, query_hash: str) -> dict[str, Any] | None:
        """Retrieves cached event listing response."""
        key = f"{EVENT_LIST_KEY_PREFIX}{query_hash}"
        try:
            cached = await self.client.get(key)
            if cached:
                return cast("dict[str, Any]", json.loads(cached))
        except Exception as exc:
            logger.warning("cache_listing_read_error", key=key, error=str(exc))
        return None

    async def set_listing(self, query_hash: str, data: dict[str, Any]) -> None:
        """Caches event listing response with shorter TTL (60s)."""
        key = f"{EVENT_LIST_KEY_PREFIX}{query_hash}"
        try:
            await self.client.setex(key, min(60, self.default_ttl), json.dumps(data, default=str))
        except Exception as exc:
            logger.warning("cache_listing_write_error", key=key, error=str(exc))
