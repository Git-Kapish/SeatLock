"""FastAPI middleware for request tracing, timing, and standardized error handling."""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ticketrush_common.errors import AppError, ErrorPayload, ErrorResponseEnvelope
from ticketrush_common.logging import bind_contextvars, clear_contextvars, get_logger

logger = get_logger("ticketrush.middleware")


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Propagates X-Request-ID, logs structured request lifecycle, and measures latency."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        start_time = time.perf_counter()
        logger.info("request_started", query_params=str(request.query_params))

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            logger.info(
                "request_completed", status_code=response.status_code, duration_ms=duration_ms
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception("request_failed", error=str(exc), duration_ms=duration_ms)
            raise


def register_error_handlers(app: FastAPI) -> None:
    """Registers standard error handlers that map domain and unhandled errors to standard envelopes."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_envelope().model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error_details: dict[str, Any] = {"errors": []}
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            err_type = err.get("type", "value_error")
            error_details["errors"].append({"location": loc, "message": msg, "type": err_type})

        envelope = ErrorResponseEnvelope(
            error=ErrorPayload(
                code="VALIDATION_ERROR",
                message="Invalid request payload or query parameters",
                details=error_details,
            )
        )
        return JSONResponse(status_code=422, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_internal_error", error=str(exc))
        envelope = ErrorResponseEnvelope(
            error=ErrorPayload(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal server error occurred.",
                details={},
            )
        )
        return JSONResponse(status_code=500, content=envelope.model_dump())
