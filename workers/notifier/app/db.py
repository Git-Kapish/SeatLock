"""Database session factory for the Notifier worker (booking schema)."""

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import config


class Base(DeclarativeBase):
    metadata = MetaData(schema="booking")


engine = create_async_engine(
    config.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_worker_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async session for background worker jobs."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
