# TicketRush 🎟️

TicketRush is a portfolio-grade, high-concurrency event ticket booking backend platform engineered to handle flash-sale concurrency.

## Key Highlights

- **Flash-Sale Concurrency Protection**: High-throughput seat holding using atomic Redis Lua scripts combined with PostgreSQL row-level locks (`SELECT ... FOR UPDATE` ordered by `seat_id`) to prevent deadlocks and overselling.
- **Strict Data Ownership**: Single PostgreSQL instance with strictly isolated schemas (`auth`, `events`, `booking`). Zero cross-schema SQL queries.
- **Clean Architecture**: `routes → services → repositories` inside every service.
- **Microservices & Async Processing**:
  - `auth-service`: JWT access/refresh token rotation, argon2 password hashing, RBAC.
  - `events-service`: Event catalog, full-text search (tsvector + GIN), Redis cache-aside.
  - `booking-service`: Inventory, atomic holds, booking lifecycle, idempotency key verification.
  - `worker-notifier`: SQS consumer, email notification dispatch, hold expiry reconciliation sweeper.
- **Observability**: Structured JSON logging with `request_id` propagation, Prometheus metrics (`/metrics`), and Grafana dashboard.

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (strict type hints with `mypy`) |
| Framework | FastAPI (async) + Pydantic v2 |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (asyncpg), Alembic |
| Cache & Locks | Redis 7 (`redis.asyncio`) |
| Queue | AWS SQS via `aioboto3` (LocalStack in development) |
| Gateway | Nginx reverse proxy |
| Orchestration | Docker Compose, Kubernetes (Kustomize, kind, k3s on AWS EC2) |
| Infrastructure | Terraform (AWS Free Tier: EC2, ECR, SQS, SES) |
| Load Testing | k6 |

## Quickstart

### Prerequisites
- Docker & Docker Compose
- `uv` (Python package manager) or Python 3.12+

### Running the Full Stack
```bash
# Start all containers (Gateway, Auth, Events, Booking, Worker, Postgres, Redis, LocalStack, MailHog)
make up

# Run database migrations
make migrate

# Run test suite
make test

# Linting & Type Checking
make lint
make typecheck
```

The services will be accessible through the API gateway at:
- Gateway: `http://localhost:8000`
- Auth API: `http://localhost:8000/api/v1/auth/docs`
- Events API: `http://localhost:8000/api/v1/events/docs`
- Booking API: `http://localhost:8000/api/v1/booking/docs`
- MailHog UI: `http://localhost:8025`
