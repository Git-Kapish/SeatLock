"""FastAPI application factory and lifecycle for Auth Service."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, health
from app.config import config
from ticketrush_common.logging import setup_logging
from ticketrush_common.middleware import RequestTracingMiddleware, register_error_handlers
from ticketrush_common.redis import RedisManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    setup_logging(service_name=config.service_name, log_level=config.log_level)
    redis_manager = RedisManager(redis_url=config.redis_url)
    app.state.redis_manager = redis_manager

    yield

    await redis_manager.close()


def create_app() -> FastAPI:
    """Builds and configures the FastAPI Auth Service application."""
    app = FastAPI(
        title="TicketRush Auth Service",
        description="User identity, authentication, JWT token rotation, and RBAC.",
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
    app.include_router(auth.router, prefix="/api/v1")

    return app


app = create_app()
