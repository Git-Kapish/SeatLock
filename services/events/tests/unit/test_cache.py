"""Unit tests for EventCache with TTL jitter and proactive invalidation."""

from unittest.mock import AsyncMock

import pytest

from app.cache import EVENT_DETAIL_KEY_PREFIX, EVENT_LIST_KEY_PREFIX, EventCache


@pytest.mark.asyncio
async def test_set_event_applies_ttl_jitter() -> None:
    """Verifies that set_event applies random jitter to TTL to prevent cache stampedes."""
    mock_redis = AsyncMock()
    cache = EventCache(redis_client=mock_redis, default_ttl=300)

    await cache.set_event("evt-123", {"title": "Rock Concert"})

    mock_redis.setex.assert_awaited_once()
    call_args = mock_redis.setex.await_args.args
    assert call_args[0] == f"{EVENT_DETAIL_KEY_PREFIX}evt-123"
    ttl = call_args[1]
    assert 300 <= ttl <= 330


@pytest.mark.asyncio
async def test_set_listing_applies_ttl_jitter() -> None:
    """Verifies that set_listing applies random jitter to base 60s TTL."""
    mock_redis = AsyncMock()
    cache = EventCache(redis_client=mock_redis, default_ttl=300)

    await cache.set_listing("hash-abc", {"items": []})

    mock_redis.setex.assert_awaited_once()
    call_args = mock_redis.setex.await_args.args
    assert call_args[0] == f"{EVENT_LIST_KEY_PREFIX}hash-abc"
    ttl = call_args[1]
    assert 60 <= ttl <= 75


@pytest.mark.asyncio
async def test_invalidate_event_deletes_detail_and_scans_listings() -> None:
    """Verifies that invalidate_event clears both the event detail and listing keys."""
    mock_redis = AsyncMock()
    # First scan returns cursor=0 and two keys
    mock_redis.scan = AsyncMock(
        return_value=(0, [f"{EVENT_LIST_KEY_PREFIX}1", f"{EVENT_LIST_KEY_PREFIX}2"])
    )
    cache = EventCache(redis_client=mock_redis)

    await cache.invalidate_event("evt-456")

    # Deletes specific event key
    mock_redis.delete.assert_any_await(f"{EVENT_DETAIL_KEY_PREFIX}evt-456")
    # Deletes listing keys found by scan
    mock_redis.delete.assert_any_await(f"{EVENT_LIST_KEY_PREFIX}1", f"{EVENT_LIST_KEY_PREFIX}2")
