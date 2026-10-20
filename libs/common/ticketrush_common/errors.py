"""Application error hierarchy and standardized error schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    """Inner payload for API error envelopes."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Structured additional error context"
    )


class ErrorResponseEnvelope(BaseModel):
    """Standard API error response wrapper across all TicketRush endpoints."""

    error: ErrorPayload


class AppError(Exception):
    """Base application exception for domain and HTTP errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers or {}

    def to_envelope(self) -> ErrorResponseEnvelope:
        return ErrorResponseEnvelope(
            error=ErrorPayload(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )


class NotFoundError(AppError):
    """Resource not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=404, details=details)


class ConflictError(AppError):
    """Resource state conflict (HTTP 409)."""

    def __init__(
        self,
        message: str = "Conflict with current resource state",
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class AuthenticationError(AppError):
    """Authentication required or failed (HTTP 401)."""

    def __init__(
        self,
        message: str = "Authentication required or credentials invalid",
        code: str = "AUTHENTICATION_FAILED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=401,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppError):
    """Action forbidden for the authenticated user/role (HTTP 403)."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=403, details=details)


class ValidationError(AppError):
    """Request data failed business or format validation (HTTP 422)."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=422, details=details)


class RateLimitError(AppError):
    """Rate limit exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
        retry_after_seconds: int = 60,
        code: str = "RATE_LIMIT_EXCEEDED",
        details: dict[str, Any] | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after_seconds)}
        payload_details = {"retry_after_seconds": retry_after_seconds, **(details or {})}
        super().__init__(
            message=message,
            code=code,
            status_code=429,
            details=payload_details,
            headers=headers,
        )


class SeatUnavailableError(ConflictError):
    """Requested seats are already held or booked (HTTP 409)."""

    def __init__(
        self,
        seat_ids: list[str],
        message: str = "One or more requested seats are unavailable",
        code: str = "SEAT_UNAVAILABLE",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details={"unavailable_seat_ids": seat_ids},
        )


class HoldExpiredError(AppError):
    """Seat hold has expired (HTTP 410)."""

    def __init__(
        self,
        hold_id: str,
        message: str = "The seat hold has expired",
        code: str = "HOLD_EXPIRED",
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=410,
            details={"hold_id": hold_id},
        )
