# ADR 0004: Idempotency Enforcement for Bookings and Payment Webhooks

## Status
Accepted

## Context
Network timeouts, mobile client retries, and duplicate payment gateway webhook deliveries can cause accidental double-charging and corrupt booking state.

## Decision
1. **Client Bookings**: `POST /api/v1/booking/bookings` requires an `Idempotency-Key` header. Requests are hashed with SHA256. If a duplicate key arrives with the exact same payload, the cached HTTP response is returned immediately. If the key is reused with a differing body, HTTP 422 (`IDEMPOTENCY_CONFLICT`) is returned.
2. **Payment Webhooks**: Inbound webhooks are verified with HMAC-SHA256 signatures (`X-Signature-256`) and recorded in `booking.processed_webhooks`. Duplicate webhook deliveries are safely skipped with HTTP 200.

## Consequences
- **Positive**: Guaranteed zero double-charges and immune to network replay loops.
- **Negative**: Requires persistent storage of idempotency hashes and cached response bodies.
