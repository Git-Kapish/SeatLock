# TicketRush — API Examples & Curl Reference

All endpoints are accessible through the Gateway on port `8000`.

---

## 1. Authentication Service (`/api/v1/auth`)

### Register User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex@example.com",
    "password": "SecurePassword123!"
  }'
```

### Log In
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex@example.com",
    "password": "SecurePassword123!"
  }'
```
Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

## 2. Events Service (`/api/v1/events`)

### List Events (Cached)
```bash
curl -X GET "http://localhost:8000/api/v1/events?status=on_sale&limit=10"
```

### Create Event (Admin Only)
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
  -d '{
    "title": "Coldplay Music of the Spheres",
    "description": "Live stadium world tour",
    "venue_name": "Wembley Stadium",
    "venue_city": "London",
    "starts_at": "2026-11-15T19:00:00Z",
    "ends_at": "2026-11-15T23:00:00Z",
    "status": "on_sale",
    "total_capacity": 50000
  }'
```

---

## 3. Booking Service (`/api/v1/booking`)

### Generate Seat Inventory Grid (Admin Only)
```bash
curl -X POST http://localhost:8000/api/v1/booking/events/<EVENT_ID>/inventory \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
  -d '{
    "tiers": [
      {
        "tier": "VIP",
        "section": "Floor-A",
        "rows": ["A", "B", "C"],
        "seats_per_row": 20,
        "price_cents": 25000
      },
      {
        "tier": "Standard",
        "section": "Tier-1",
        "rows": ["D", "E", "F", "G"],
        "seats_per_row": 30,
        "price_cents": 12000
      }
    ]
  }'
```

### Get Real-Time Seat Availability Map (Public)
```bash
curl -X GET http://localhost:8000/api/v1/booking/events/<EVENT_ID>/seats
```

### Acquire Atomic Seat Hold (Authenticated, Rate-Limited: 10 req/min)
```bash
curl -X POST http://localhost:8000/api/v1/booking/holds \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <USER_JWT_TOKEN>" \
  -d '{
    "event_id": "<EVENT_ID>",
    "seat_ids": [
      "<SEAT_ID_1>",
      "<SEAT_ID_2>"
    ]
  }'
```
Response (`201 Created`):
```json
{
  "id": "7b8e1f2a-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "event_id": "<EVENT_ID>",
  "user_id": "<USER_ID>",
  "status": "active",
  "expires_at": "2026-10-21T10:10:00Z",
  "seats": [
    { "id": "<SEAT_ID_1>", "section": "Floor-A", "row": "A", "seat_number": 1 },
    { "id": "<SEAT_ID_2>", "section": "Floor-A", "row": "A", "seat_number": 2 }
  ]
}
```

### Create Idempotent Booking (Authenticated, Rate-Limited: 5 req/min)
```bash
curl -X POST http://localhost:8000/api/v1/booking/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <USER_JWT_TOKEN>" \
  -H "Idempotency-Key: e4b2d6a8-1234-5678-90ab-cdef12345678" \
  -d '{
    "hold_id": "7b8e1f2a-3c4d-5e6f-7a8b-9c0d1e2f3a4b"
  }'
```
Response (`201 Created`):
```json
{
  "id": "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "user_id": "<USER_ID>",
  "event_id": "<EVENT_ID>",
  "hold_id": "7b8e1f2a-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "status": "pending_payment",
  "total_cents": 50000,
  "client_secret": "cs_test_9f8e7d6c5b4a3a2b1c",
  "created_at": "2026-10-21T10:01:00Z"
}
```

### Simulate Payment Webhook (HMAC-SHA256 Signature Verification)
```bash
# Payload
PAYLOAD='{"event_id":"evt_test_123","event_type":"payment.succeeded","occurred_at":"2026-10-21T10:02:00Z","data":{"booking_id":"<BOOKING_ID>","amount_cents":50000}}'

# Compute HMAC signature using webhook secret
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "development-payment-webhook-secret-key-min-32-chars" | sed 's/^.* //')

curl -X POST http://localhost:8000/api/v1/booking/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD"
```
Response (`200 OK`):
```json
{
  "status": "processed",
  "event_id": "evt_test_123",
  "booking_id": "<BOOKING_ID>",
  "booking_status": "confirmed"
}
```
