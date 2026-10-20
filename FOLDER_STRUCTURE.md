# TicketRush — Folder Structure

A **monorepo**: one repo, independent services, one shared library. Each service is its own deployable image with its own dependencies.

```
ticketrush/
├── CLAUDE.md                      # Instructions for Claude Code (read every session)
├── README.md                      # Quickstart, architecture diagram, load test results
├── Makefile                       # make up / down / test / lint / migrate / load-test
├── docker-compose.yml             # Full local stack
├── docker-compose.override.yml    # Local dev tweaks (hot reload, mounts)
├── pyproject.toml                 # Root tooling config: ruff, mypy, pytest
├── .env.example                   # Every env var documented, no real secrets
├── .gitignore
├── .pre-commit-config.yaml
│
├── libs/
│   └── common/                    # Shared package, installed into every service
│       ├── pyproject.toml
│       └── ticketrush_common/
│           ├── config.py          # Base pydantic-settings
│           ├── logging.py         # Structured JSON logging + request-id context
│           ├── errors.py          # AppError hierarchy + error response schema
│           ├── middleware.py      # Request ID, timing, exception handlers
│           ├── security.py        # JWT decode/verify, role dependencies
│           ├── redis.py           # Redis client factory, rate limiter (token bucket)
│           ├── sqs.py             # aioboto3 publisher/consumer helpers
│           ├── metrics.py         # Prometheus instrumentation
│           └── pagination.py      # Shared pagination schemas
│
├── services/
│   ├── auth/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/            # Alembic (schema: auth)
│   │   │   └── versions/
│   │   ├── app/
│   │   │   ├── main.py            # FastAPI app factory, lifespan, routers
│   │   │   ├── config.py
│   │   │   ├── api/
│   │   │   │   ├── deps.py        # DB session, current user dependencies
│   │   │   │   └── routes/
│   │   │   │       ├── auth.py
│   │   │   │       └── health.py
│   │   │   ├── models/            # SQLAlchemy models
│   │   │   ├── schemas/           # Pydantic request/response models
│   │   │   ├── repositories/      # DB access only
│   │   │   ├── services/          # Business logic (hashing, token rotation)
│   │   │   └── db.py              # Async engine + session factory
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── unit/
│   │       └── integration/
│   │
│   ├── events/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── api/routes/        # events.py, internal.py, health.py
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── repositories/
│   │   │   ├── services/          # event_service.py, search, cache invalidation
│   │   │   ├── cache.py           # Redis cache-aside helpers
│   │   │   └── db.py
│   │   └── tests/
│   │
│   └── booking/                   # Core service
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── alembic.ini
│       ├── migrations/
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── api/routes/        # inventory.py, seats.py, holds.py,
│       │   │                      # bookings.py, webhooks.py, admin.py, health.py
│       │   ├── models/            # seat, hold, booking, payment, idempotency_key
│       │   ├── schemas/
│       │   ├── repositories/
│       │   ├── services/
│       │   │   ├── hold_service.py        # Redis Lua + DB locking
│       │   │   ├── booking_service.py     # Orchestrates hold → pay → confirm
│       │   │   ├── payment_service.py     # Mock provider + webhook verify
│       │   │   ├── idempotency.py
│       │   │   └── inventory_service.py
│       │   ├── clients/
│       │   │   └── events_client.py       # HTTP client to events-service (timeouts, retries)
│       │   ├── redis_scripts/
│       │   │   └── acquire_holds.lua
│       │   └── db.py
│       └── tests/
│           ├── unit/
│           ├── integration/
│           └── concurrency/       # Race-condition tests (asyncio.gather on same seat)
│
├── workers/
│   └── notifier/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── app/
│       │   ├── main.py            # Consumer loop, graceful shutdown
│       │   ├── handlers/          # booking_confirmed.py, payment_webhook.py
│       │   ├── sweeper.py         # Expired-hold reconciliation job
│       │   ├── email.py           # SES / SMTP (MailHog) adapter
│       │   └── retry.py           # Backoff + DLQ logic
│       └── tests/
│
├── gateway/
│   ├── nginx.conf                 # Routing + coarse rate limit (local/compose)
│   └── Dockerfile
│
├── deploy/
│   ├── k8s/
│   │   ├── base/                  # Deployments, Services, ConfigMaps, HPA, probes,
│   │   │                          # migration Jobs, Ingress
│   │   └── overlays/
│   │       ├── local/             # kind/minikube
│   │       └── aws/               # k3s on EC2 (ECR image refs, real secrets refs)
│   ├── terraform/
│   │   ├── main.tf                # EC2, security groups, IAM
│   │   ├── ecr.tf
│   │   ├── sqs.tf
│   │   ├── ses.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md              # How to apply and tear down
│   └── scripts/
│       ├── bootstrap-k3s.sh
│       ├── deploy.sh
│       └── teardown.sh
│
├── observability/
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── dashboards/ticketrush.json
│       └── provisioning/
│
├── loadtest/
│   ├── k6/
│   │   ├── flash_sale.js          # 1,000 users vs 100 seats
│   │   ├── browse.js              # Cached read load
│   │   └── README.md              # How to run + how to verify zero oversell
│   ├── seed.py                    # Seed users, event, inventory
│   └── verify_invariants.sql      # Post-run DB checks
│
├── docs/
│   ├── architecture.md            # Diagram, service responsibilities, decisions
│   ├── concurrency.md             # Hold/booking flows, locking, invariants
│   ├── api-examples.md
│   ├── runbook.md                 # Deploy, rollback, debugging
│   ├── adr/                       # Architecture Decision Records (0001-*.md ...)
│   └── postman/ticketrush.postman_collection.json
│
└── .github/
    └── workflows/
        ├── ci.yml                 # Lint, type check, test, build
        └── deploy.yml             # Push to ECR, deploy to AWS, smoke test
```

## Layering Rule (inside every service)

```
routes (HTTP only)  →  services (business logic)  →  repositories (DB only)
        ↓                       ↓                            ↓
     schemas               models + clients               models
```

- **Routes** parse and validate input, call one service method, return a schema. No business logic, no SQL.
- **Services** hold the rules and transactions. They never import FastAPI types.
- **Repositories** are the only code that touches SQLAlchemy queries.

This keeps logic unit-testable without HTTP or a database.

## Why a monorepo with a shared lib

- One clone, one `docker compose up`, one CI pipeline.
- Cross-cutting code (logging, errors, JWT verification, Redis helpers) is written once.
- Services still deploy independently, and each has its own Dockerfile, migrations, and tests.
- Keep `libs/common` small and free of business logic. It must never import from a service.
