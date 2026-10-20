"""Prometheus instrumentation and metrics definitions."""

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Standard metrics
REQUEST_COUNT = Counter(
    "ticketrush_http_requests_total",
    "Total HTTP requests received",
    ["service", "method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "ticketrush_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_SEAT_HOLDS = Gauge(
    "ticketrush_active_seat_holds",
    "Current number of actively held seats across events",
    ["service"],
)

BOOKINGS_TOTAL = Counter(
    "ticketrush_bookings_total",
    "Total booking transactions finalized",
    ["service", "status"],
)


def metrics_endpoint_response() -> Response:
    """Generates the latest Prometheus metrics in standard text format."""
    content: bytes = bytes(generate_latest())
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)
