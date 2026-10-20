from ticketrush_common.errors import (
    AppError,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    SeatUnavailableError,
)


def test_app_error_to_envelope():
    err = AppError(
        message="Something failed", code="CUSTOM_FAIL", status_code=400, details={"foo": "bar"}
    )
    envelope = err.to_envelope()
    assert envelope.error.code == "CUSTOM_FAIL"
    assert envelope.error.message == "Something failed"
    assert envelope.error.details == {"foo": "bar"}


def test_not_found_error():
    err = NotFoundError("User not found")
    assert err.status_code == 404
    assert err.code == "NOT_FOUND"


def test_authentication_error():
    err = AuthenticationError("Invalid token")
    assert err.status_code == 401
    assert err.headers.get("WWW-Authenticate") == "Bearer"


def test_forbidden_error():
    err = ForbiddenError("Requires admin")
    assert err.status_code == 403
    assert err.code == "FORBIDDEN"


def test_rate_limit_error():
    err = RateLimitError(retry_after_seconds=30)
    assert err.status_code == 429
    assert err.headers.get("Retry-After") == "30"
    assert err.details.get("retry_after_seconds") == 30


def test_seat_unavailable_error():
    err = SeatUnavailableError(seat_ids=["seat-1", "seat-2"])
    assert err.status_code == 409
    assert err.code == "SEAT_UNAVAILABLE"
    assert err.details["unavailable_seat_ids"] == ["seat-1", "seat-2"]
