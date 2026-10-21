"""Repository for IdempotencyKey records."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency import IdempotencyKey


class IdempotencyRepository:
    """Stores and retrieves idempotency keys to ensure exactly-once execution."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_key(self, key: str) -> IdempotencyKey | None:
        """Retrieves cached response record for an idempotency key."""
        stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_key(self, record: IdempotencyKey) -> IdempotencyKey:
        """Persists a new idempotency key record."""
        self.session.add(record)
        await self.session.flush()
        return record
