"""Health check and readiness endpoints for Booking service."""

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from ticketrush_common.metrics import metrics_endpoint_response

router = APIRouter(tags=["Health"])


@router.get("/health/live", status_code=status.HTTP_200_OK, summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Basic liveness probe confirming process is responsive."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None, summary="Readiness probe")
async def readiness(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Readiness probe checking database and Redis connectivity."""
    checks: dict[str, str] = {}

    # Check Database
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"

    # Check Redis
    try:
        client = getattr(request.app.state, "redis_client", None)
        if client:
            await client.ping()
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unhealthy: client not initialized"
    except Exception as exc:
        checks["redis"] = f"unhealthy: {exc}"

    is_ready = all(status_str == "healthy" for status_str in checks.values())
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={"status": "ready" if is_ready else "not_ready", "checks": checks},
        status_code=status_code,
    )


@router.get("/metrics", summary="Prometheus metrics")
async def metrics() -> Response:
    """Prometheus exposition format endpoint."""
    return metrics_endpoint_response()
