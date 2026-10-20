"""Alembic async environment script for Events schema."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import config
from app.db import Base
from app.models import Event  # noqa: F401

alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    # Ensure events schema exists
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS events;"))

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="events",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(config.database_url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    context.configure(
        url=config.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema="events",
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
