"""Idempotency service ensuring non-replayable transactional API requests."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from app.models.idempotency import IdempotencyKey
from app.repositories.idempotency_repository import IdempotencyRepository
from ticketrush_common.errors import ValidationError


class IdempotencyService:
    """Manages idempotency key lookup, conflict detection, and response caching."""

    def __init__(self, idempotency_repo: IdempotencyRepository) -> None:
        self.repo = idempotency_repo

    @staticmethod
    def compute_hash(payload_bytes: bytes) -> str:
        """Returns the SHA256 hex digest of the raw request payload."""
        return hashlib.sha256(payload_bytes).hexdigest()

    async def check_idempotency(
        self,
        key: str,
        user_id: uuid.UUID,
        payload_bytes: bytes,
    ) -> tuple[int, str] | None:
        """Checks if a request with this key was already processed.

        Returns:
            tuple[int, str] containing (status_code, response_body) if replay.
            None if this is a fresh key that can be processed.

        Raises:
            ValidationError: If the key was already used with a different request payload.
        """
        record = await self.repo.get_key(key)
        if not record:
            return None

        current_hash = self.compute_hash(payload_bytes)
        if record.request_hash != current_hash:
            raise ValidationError(
                message="Idempotency key reused with a different request payload",
                code="IDEMPOTENCY_CONFLICT",
                details={"key": key},
            )

        return record.status_code, record.response_body

    async def save_idempotency_record(
        self,
        key: str,
        user_id: uuid.UUID,
        payload_bytes: bytes,
        status_code: int,
        response_body: str,
    ) -> None:
        """Persists response output under the idempotency key for future replay."""
        record = IdempotencyKey(
            key=key,
            user_id=user_id,
            request_hash=self.compute_hash(payload_bytes),
            response_body=response_body,
            status_code=status_code,
            created_at=datetime.now(UTC),
        )
        await self.repo.save_key(record)
