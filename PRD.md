# TicketRush — Product Requirements Document

**Version:** 1.0 | **Stack:** Python 3.12, FastAPI, PostgreSQL, Redis, SQS | **Target:** Portfolio backend project for software engineering roles

---

## 1. Overview

TicketRush is a backend platform for booking tickets to live events (concerts, matches, shows). Its defining challenge is **flash-sale concurrency**: thousands of users competing for a few hundred seats at the same moment, with zero double bookings, graceful payment failures, and automatic scaling.

There is no required frontend. A Swagger UI and a Postman collection are the "client". A minimal React or HTML page is optional.

### 1.1 Goals

1. Demonstrate production-style backend engineering: auth, transactions, caching, async processing, idempotency, rate limiting, observability.
2. Prove correctness under load: **1,000 concurrent users vs 100 seats = exactly 100 confirmed bookings, 0 oversells** (k6 report in README).
3. Be fully containerized, deployable to Kubernetes, and deployed on AWS free tier via CI/CD and Terraform.

### 1.2 Non-Goals

- Real payment gateway integration (use a mock provider with a webhook).
- Seat-map UI, mobile apps, recommendation engine, multi-region setup.
- More than 3 services plus 1 worker. Depth beats breadth.

### 1.3 Personas

| Persona | Needs |
|---|---|
| **Attendee** | Browse and search events, hold seats, pay, receive confirmation, view or cancel bookings |
| **Organizer/Admin** | Create events, define seat inventory and pricing, view sales |
| **Interviewer/Reviewer** | Clone the repo, run `docker compose up`, see it work in 5 minutes |

---

## 2. System Architecture

```
Client ──► Nginx / Ingress (routing, TLS, coarse rate limit)
              ├──► auth-service      (users, JWT)
              ├──► events-service    (catalog, search, cache)
              └──► booking-service   (seats, holds, bookings, payments)
                        │ publishes
                        ▼
                      SQS queues ──► worker (notifications, payment webhooks, hold expiry)

Shared infra: PostgreSQL (one instance, one schema per service), Redis (cache, locks, holds, rate limits)
```

### 2.1 Key Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| Service data ownership | Separate Postgres **schema** per service; no cross-schema queries | Real boundaries, one cheap instance |
| Service-to-service calls | Sync HTTP for validation (booking → events); async SQS for side effects | Keeps flows simple, side effects retryable |
| Queue | SQS via `aioboto3`; **LocalStack** in docker-compose | One implementation for local and AWS |
| Source of truth for seats | PostgreSQL | Redis holds are an optimization, never the authority |
| Auth between services | Gateway validates JWT; internal calls use a shared internal service token | Simple and sufficient |
| Async | FastAPI async + SQLAlchemy 2.0 async + asyncpg | Handles high concurrency efficiently |

---

## 3. Functional Requirements

Priority: **P0** = must ship, **P1** = should ship, **P2** = nice to have.

### 3.1 Auth Service

| ID | Requirement | Pri |
|---|---|---|
| A1 | Register with email + password (argon2/bcrypt hashing, password rules) | P0 |
| A2 | Login returns short-lived access JWT (15 min) + refresh token (7 days) | P0 |
| A3 | Refresh endpoint with refresh-token rotation; revoked tokens stored in Redis | P0 |
| A4 | Roles: `user`, `admin`. Admin-only dependency guard | P0 |
| A5 | `GET /me`, logout (revoke refresh token) | P0 |
| A6 | Rate limit login: 5 attempts/min per IP+email | P1 |

Endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`

### 3.2 Events Service

| ID | Requirement | Pri |
|---|---|---|
| E1 | Admin CRUD on events (title, description, venue, city, category, starts_at, status) | P0 |
| E2 | Public list with **cursor or offset pagination**, filters (city, category, date range), sorting | P0 |
| E3 | Full-text search on title/description (Postgres `tsvector` + GIN index) | P1 |
| E4 | Redis cache for event detail and list pages; invalidate on update | P0 |
| E5 | Event status lifecycle: `draft → published → on_sale → sold_out → completed / cancelled` | P0 |
| E6 | Internal endpoint for booking-service to validate an event is `on_sale` | P0 |

Endpoints: `GET /events`, `GET /events/{id}`, `POST /events` (admin), `PATCH /events/{id}` (admin), `DELETE /events/{id}` (admin, soft delete), `GET /internal/events/{id}`

### 3.3 Booking Service (core)

| ID | Requirement | Pri |
|---|---|---|
| B1 | Admin generates seat inventory for an event (sections, rows, seats, price tier) | P0 |
| B2 | `GET /events/{id}/seats` returns seat availability (available, held, booked), cached briefly | P0 |
| B3 | **Hold seats**: user selects 1–6 seats; all-or-nothing; hold expires in 10 minutes | P0 |
| B4 | **Confirm booking**: initiate payment against an active hold, requires `Idempotency-Key` header | P0 |
| B5 | Payment mock provider: creates a payment intent; result delivered via webhook (success, failure, delay) | P0 |
| B6 | On payment success: seats → `booked`, booking → `confirmed`, publish `booking.confirmed` | P0 |
| B7 | On payment failure or hold expiry: seats released, booking → `failed` / `expired` | P0 |
| B8 | User can list own bookings and cancel a confirmed booking (before event cutoff); seats released | P1 |
| B9 | Per-user limit: max 6 seats per event; max 3 active holds | P1 |
| B10 | Rate limit hold and booking endpoints (Redis token bucket) | P0 |
| B11 | Admin sales summary: seats sold, revenue, occupancy per event | P1 |

Endpoints: `POST /booking/events/{id}/inventory` (admin), `GET /booking/events/{id}/seats`, `POST /booking/holds`, `DELETE /booking/holds/{id}`, `POST /booking/bookings` (with Idempotency-Key), `GET /booking/bookings`, `GET /booking/bookings/{id}`, `POST /booking/bookings/{id}/cancel`, `POST /booking/payments/webhook`

### 3.4 Worker

| ID | Requirement | Pri |
|---|---|---|
| W1 | Consume `booking.confirmed` and send confirmation email (SES on AWS, console/MailHog locally) | P0 |
| W2 | Consume `payment.webhook_received` for processing with retry and exponential backoff | P0 |
| W3 | Dead-letter queue after N failed attempts; admin endpoint or script to inspect and redrive | P1 |
| W4 | Periodic sweeper: release expired holds that Redis TTL missed (DB reconciliation) | P0 |
| W5 | Handlers are idempotent (processing the same message twice is safe) | P0 |

---

## 4. Concurrency & Correctness Strategy

This is the centerpiece. Document it in `docs/concurrency.md`.

### 4.1 Seat Hold Flow (all-or-nothing)

1. Validate request, rate limit, per-user limits.
2. Try to acquire Redis keys `hold:{event_id}:{seat_id}` with `SET NX EX 600` for each seat (via Lua script so it is atomic across all seats).
3. If any seat fails, roll back the acquired keys and return `409 Conflict` listing unavailable seats.
4. Inside one Postgres transaction: `SELECT ... FOR UPDATE` the seat rows (ordered by seat id to avoid deadlocks), verify `status = 'available'`, insert a `holds` row, set seats to `held`.
5. Return `hold_id` and `expires_at`.

Redis gives fast rejection under load; **Postgres row locks are the correctness guarantee**. If Redis is down, the system degrades to DB-only and stays correct.

### 4.2 Booking & Payment Flow

1. `POST /bookings` with `Idempotency-Key`. Look up the key in `idempotency_keys` (unique constraint). If found, return the stored response.
2. Verify the hold belongs to the user and has not expired.
3. Create `booking` (`pending_payment`) and `payment` (`initiated`) rows; call the mock provider.
4. Webhook arrives: verify signature, dedupe by provider event id, update state in one transaction.
5. Success: seats `booked`, booking `confirmed`, publish `booking.confirmed`. Failure: release seats.

### 4.3 Invariants (tested)

- A seat is in `booked` status for at most one confirmed booking (partial unique index).
- A hold never extends beyond its `expires_at`.
- The same idempotency key never creates two bookings.
- Total confirmed seats for an event never exceeds its inventory.

---

## 5. Data Model (summary)

| Schema | Table | Key columns |
|---|---|---|
| auth | `users` | id (uuid), email (unique), password_hash, role, created_at |
| auth | `refresh_tokens` | id, user_id, token_hash, expires_at, revoked_at |
| events | `events` | id, title, description, venue, city, category, starts_at, status, search_vector, deleted_at |
| booking | `seats` | id, event_id, section, row, number, price_cents, status (`available/held/booked`), version |
| booking | `holds` | id, user_id, event_id, status, expires_at |
| booking | `hold_seats` | hold_id, seat_id |
| booking | `bookings` | id, user_id, event_id, hold_id, status, total_cents, created_at |
| booking | `booking_seats` | booking_id, seat_id (partial unique index on active bookings) |
| booking | `payments` | id, booking_id, provider_ref, status, amount_cents, created_at |
| booking | `idempotency_keys` | key, user_id, request_hash, response_body, status_code, created_at |
| booking | `processed_webhooks` | provider_event_id (unique), processed_at |

Money is stored as integer cents. All timestamps are UTC `timestamptz`. Indexes on `(event_id, status)` for seats, `(user_id, created_at)` for bookings.

---

## 6. API Conventions

- Base path per service; versioned as `/api/v1/...`.
- JSON only. Pydantic v2 request and response schemas.
- Error format: `{"error": {"code": "SEAT_UNAVAILABLE", "message": "...", "details": {...}}}`
- Standard codes: 400 validation, 401, 403, 404, 409 conflict, 422, 429 with `Retry-After`.
- Every response carries `X-Request-ID`; propagated through logs and service calls.
- OpenAPI docs auto-generated; every endpoint has summary, schema examples, and error responses.

---

## 7. Non-Functional Requirements

| Area | Target |
|---|---|
| Correctness | 0 double bookings under load test |
| Performance | Event list (cached) p95 < 100 ms; hold endpoint p95 < 300 ms at 200 rps on a single small instance |
| Availability | Readiness/liveness probes; graceful shutdown; zero-downtime rolling deploys |
| Security | Hashed passwords, JWT validation, input validation, secrets via env/K8s Secrets (never committed), CORS config, dependency scanning |
| Observability | Structured JSON logs with request id, `/metrics` (Prometheus), Grafana dashboard (requests, latency, errors, holds, bookings) |
| Testing | Unit + integration (real Postgres/Redis via testcontainers or compose); coverage ≥ 80% on service logic |
| Portability | Everything runs with one command locally |

---

## 8. Infrastructure & DevOps Requirements

### 8.1 Docker
- Multi-stage Dockerfile per service, non-root user, slim base image, `.dockerignore`, health check.
- `docker-compose.yml`: gateway, 3 services, worker, Postgres, Redis, LocalStack (SQS), MailHog, Prometheus, Grafana.

### 8.2 Kubernetes
- Manifests (Kustomize, `base` + `overlays/local` + `overlays/aws`) for: Deployments, Services, ConfigMaps, Secrets, Ingress, HPA (on CPU), liveness/readiness/startup probes, resource requests and limits, a migration Job.
- Local: `kind` or `minikube`. AWS: **k3s on EC2**.

### 8.3 AWS (free tier)
- EC2 (t3.micro) running k3s, or EC2 + Docker Compose as documented fallback; ECR for images; SQS; SES (sandbox); CloudWatch logs; optional RDS `db.t3.micro` (otherwise Postgres in-cluster).
- Provisioned with **Terraform** (VPC, security groups, EC2, ECR, SQS, IAM roles with least privilege).
- Budget alert set before anything else. Verify current free-tier terms before starting.

### 8.4 CI/CD (GitHub Actions)
- On PR: lint (ruff), type check (mypy), tests, build images.
- On merge to `main`: push images to ECR, deploy to the AWS environment, run smoke test.

---

## 9. Milestones & Acceptance Criteria

| Phase | Weeks | Deliverables | Done when |
|---|---|---|---|
| 1. Foundations | 1 | Repo, shared lib, auth + events services, Postgres, Alembic migrations, Dockerfiles | Register/login works; admin creates events; tests pass in CI |
| 2. Booking core | 2 | Inventory, seat listing, holds with Redis + DB locking | 50 parallel requests for one seat yield exactly one hold |
| 3. Payments & async | 3 | Idempotent booking, mock payment + webhook, SQS worker, retries, DLQ | Duplicate requests and duplicate webhooks produce one booking; failed emails retry then land in DLQ |
| 4. Hardening | 4 | Caching, rate limiting, error handling, full test suite, k6 load test | k6: 1,000 users vs 100 seats = 100 bookings, 0 oversells; results in README |
| 5. Kubernetes | 5 | docker-compose finalized, K8s manifests, HPA, probes | `kubectl apply` brings up the stack on kind; HPA scales under load |
| 6. Cloud & CI/CD | 6 | GitHub Actions, Terraform, AWS deploy | Push to main deploys; public URL serves Swagger |
| 7. Polish | 7–8 | Prometheus/Grafana, docs, diagrams, demo video | A stranger can run it in 5 minutes from the README |

---

## 10. Success Metrics

- Load test report proving zero oversells.
- All P0 requirements shipped; ≥ 80% of P1.
- Live deployed URL and a 3-minute demo video.
- README with architecture diagram, concurrency write-up, load test results, and a "trade-offs and what I'd do next" section.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Scope creep into more microservices | Hard cap at 3 services + 1 worker |
| AWS free-tier changes or surprise bills | Budget alerts; teardown script; local-first development |
| t3.micro memory pressure running k3s + Postgres + Redis | Use RDS for Postgres, or fall back to Compose on EC2; K8s demo on kind |
| Concurrency bugs hard to reproduce | Write the load and race tests early (Phase 2), not at the end |
| Distributed complexity slows progress | Finish each phase fully before the next; keep sync HTTP minimal |

## 12. Interview Talking Points (design for these)

1. How do you prevent double booking? (Redis fast path + Postgres row locks, ordered locking to avoid deadlock)
2. What if payment succeeds but your server crashes? (webhook retries, idempotent handlers, reconciliation sweeper)
3. What if the user double-clicks Pay? (idempotency keys)
4. How does it scale? (stateless services, HPA, cache, queue-based side effects)
5. What would you change at 100x scale? (partition seats by event, dedicated inventory service, read replicas, queue-based waiting room)
