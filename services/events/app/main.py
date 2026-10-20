"""FastAPI application factory and lifecycle for Events Service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.api.routes import events, health, internal
from app.config import config
from ticketrush_common.logging import setup_logging
from ticketrush_common.middleware import RequestTracingMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    setup_logging(service_name=config.service_name, log_level=config.log_level)
    redis_client = aioredis.from_url(config.redis_url, decode_responses=True)
    app.state.redis_client = redis_client

    yield

    await redis_client.close()


def create_app() -> FastAPI:
    """Builds and configures the FastAPI Events Service application."""
    app = FastAPI(
        title="TicketRush Events Service",
        description="Event catalog, search, status lifecycle, and caching.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Middleware & Error handling
    app.add_middleware(RequestTracingMiddleware)
    register_error_handlers(app)

    # Register Routers
    app.include_router(health.router)
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(internal.router, prefix="/api/v1")

    return app


app = create_app()
