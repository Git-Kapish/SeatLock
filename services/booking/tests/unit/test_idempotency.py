"""Unit tests for IdempotencyService."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.idempotency import IdempotencyKey
from app.services.idempotency_service import IdempotencyService
from ticketrush_common.errors import ValidationError


@pytest.mark.asyncio
async def test_fresh_idempotency_key() -> None:
    repo = AsyncMock()
    repo.get_key.return_value = None

    service = IdempotencyService(repo)
    user_id = uuid.uuid4()
    key = "idem-test-key-1"
    payload = b'{"hold_id": "123"}'

    res = await service.check_idempotency(key, user_id, payload)
    assert res is None
    repo.get_key.assert_called_once_with(key)


@pytest.mark.asyncio
async def test_replay_identical_idempotency_key() -> None:
    repo = AsyncMock()
    user_id = uuid.uuid4()
    key = "idem-test-key-2"
    payload = b'{"hold_id": "123"}'
    hash_val = IdempotencyService.compute_hash(payload)

    record = IdempotencyKey(
        key=key,
        user_id=user_id,
        request_hash=hash_val,
        response_body='{"booking_id": "b-1"}',
        status_code=201,
    )
    repo.get_key.return_value = record

    service = IdempotencyService(repo)
    res = await service.check_idempotency(key, user_id, payload)

    assert res is not None
    status_code, body = res
    assert status_code == 201
    assert body == '{"booking_id": "b-1"}'


@pytest.mark.asyncio
async def test_conflicting_idempotency_payload_raises() -> None:
    repo = AsyncMock()
    user_id = uuid.uuid4()
    key = "idem-test-key-3"
    original_payload = b'{"hold_id": "123"}'
    different_payload = b'{"hold_id": "456"}'
    original_hash = IdempotencyService.compute_hash(original_payload)

    record = IdempotencyKey(
        key=key,
        user_id=user_id,
        request_hash=original_hash,
        response_body='{"booking_id": "b-1"}',
        status_code=201,
    )
    repo.get_key.return_value = record

    service = IdempotencyService(repo)
    with pytest.raises(ValidationError) as exc_info:
        await service.check_idempotency(key, user_id, different_payload)

    assert exc_info.value.code == "IDEMPOTENCY_CONFLICT"
