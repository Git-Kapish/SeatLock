"""Data access repository for users and refresh tokens in auth schema."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.models.user import User


class UserRepository:
    """Encapsulates all database queries on the auth schema."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        """Finds a user by normalized lowercase email."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Finds a user by unique UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, email: str, password_hash: str, role: str = "user") -> User:
        """Persists a new user record."""
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            password_hash=password_hash,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Persists a newly issued refresh token hash."""
        token_record = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token_record)
        await self.session.flush()
        return token_record

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        """Finds an active or revoked refresh token record."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Marks a refresh token as revoked."""
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked_at=now)
        )
        await self.session.execute(stmt)

    async def revoke_all_user_refresh_tokens(self, user_id: uuid.UUID) -> None:
        """Revokes all active refresh tokens belonging to a user."""
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
