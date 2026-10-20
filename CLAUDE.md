# CLAUDE.md — TicketRush

Read this fully at the start of every session. Also read `docs/PRD.md` (the source of truth for requirements) and `docs/architecture.md` once they exist.

## What this project is

TicketRush is a high-concurrency event ticket booking backend: 3 FastAPI services (`auth`, `events`, `booking`) plus 1 async worker (`notifier`), on PostgreSQL, Redis and SQS. It runs in Docker Compose locally, on Kubernetes (kind locally, k3s on AWS EC2), and deploys to AWS free tier via GitHub Actions and Terraform.

The goal is a portfolio-grade project for a fresher backend engineer. Correctness under concurrency, clean structure and good documentation matter more than feature count. **Do not add services or features beyond the PRD.**

## Tech stack (do not substitute without asking)

| Concern | Choice |
|---|---|
| Language | Python 3.12, fully type-hinted |
| Framework | FastAPI (async), Pydantic v2, pydantic-settings |
| DB | PostgreSQL 16, SQLAlchemy 2.0 **async** (asyncpg), Alembic |
| Cache / locks / rate limit | Redis 7 via `redis.asyncio` |
| Queue | SQS via `aioboto3`; LocalStack in local dev |
| Auth | JWT (PyJWT), argon2-cffi for password hashing |
| HTTP client | httpx (async) with timeouts and retries |
| Tests | pytest, pytest-asyncio, httpx AsyncClient, testcontainers |
| Lint / types | ruff (lint + format), mypy (strict on `libs/` and `app/`) |
| Packaging | `uv` with `pyproject.toml` per service |
| Observability | structlog JSON logs, `prometheus-client`, Grafana |
| Load test | k6 |

## Repo layout

See `docs/FOLDER_STRUCTURE.md`. Summary:

- `libs/common/` — shared package (`ticketrush_common`): config, logging, errors, JWT verify, Redis, SQS helpers. No business logic. Never imports from services.
- `services/{auth,events,booking}/` — each has `app/`, `migrations/`, `tests/`, `Dockerfile`.
- `workers/notifier/` — SQS consumer + hold sweeper.
- `deploy/` (k8s, terraform, scripts), `observability/`, `loadtest/`, `docs/`, `.github/workflows/`.

## Commands

```bash
make up              # docker compose up --build (full stack)
make down            # stop and remove containers
make migrate         # run Alembic migrations for all services
make test            # all tests
make test-svc S=booking   # tests for one service
make lint            # ruff check + ruff format --check
make fmt             # ruff format + ruff check --fix
make typecheck       # mypy
make load-test       # k6 flash-sale test (stack must be up)
make k8s-local       # create kind cluster + apply overlays/local
```

If a command in the Makefile does not exist yet, create it rather than running ad-hoc commands, so the Makefile stays the single entry point.

## Architecture rules

1. **Layering inside each service:** `routes → services → repositories`.
   - Routes: parse/validate, call one service method, return a schema. No SQL, no business logic.
   - Services: business rules and transaction boundaries. No FastAPI imports.
   - Repositories: the only place SQLAlchemy queries live.
2. **Data ownership:** each service owns one Postgres schema (`auth`, `events`, `booking`). **Never query another service's schema.** Cross-service needs go through HTTP (sync, for validation) or SQS (async, for side effects).
3. **Postgres is the source of truth.** Redis holds, caches and rate limits are optimizations; the system must stay correct if Redis is empty or down.
4. **Money** is integer cents. **Timestamps** are UTC `timestamptz`. **IDs** are UUIDs.
5. **Config** comes only from environment variables via pydantic-settings. No hardcoded secrets, hosts or ports. Every new variable goes in `.env.example`.
6. **All I/O is async.** Never call blocking code (requests, sync SQLAlchemy, `time.sleep`) in a request path.

## Concurrency & correctness rules (most important)

- Seat holds: acquire Redis keys atomically via a Lua script (all-or-nothing), then in one DB transaction `SELECT ... FOR UPDATE` the seats **ordered by seat id** (prevents deadlocks), verify availability, and write.
- Hold TTL is 10 minutes. A background sweeper reconciles expired holds in the DB.
- `POST /bookings` requires an `Idempotency-Key`; store key + request hash + response in `idempotency_keys` with a unique constraint. Same key + different body = 422.
- Payment webhooks are deduped by provider event id (`processed_webhooks`) and must be safe to process twice.
- All queue handlers are idempotent. Retries use exponential backoff; after N attempts the message goes to the DLQ.
- DB constraints back up application logic (partial unique index so a seat can belong to only one active booking).
- Any change touching holds, bookings or payments **must** come with a concurrency test in `tests/concurrency/` (e.g. `asyncio.gather` of 50 requests for the same seat → exactly 1 succeeds).

## Coding conventions

- Type hints everywhere; `mypy` must pass. No `Any` unless justified in a comment.
- Pydantic schemas for every request and response. Never return ORM models directly.
- Errors: raise `AppError` subclasses from `ticketrush_common.errors`; the shared handler formats `{"error": {"code", "message", "details"}}`. Never leak stack traces or internal messages to clients.
- Use correct status codes: 400/422 validation, 401, 403, 404, 409 conflicts, 429 with `Retry-After`.
- Logging: structured JSON, include `request_id`. Never log passwords, tokens, or full payment data.
- Every endpoint has a summary, response model, and documented error responses in OpenAPI.
- Every service exposes `GET /health/live`, `GET /health/ready` (checks DB/Redis), and `GET /metrics`.
- Keep functions small and named for intent. Prefer clarity over cleverness. Comments explain *why*, not *what*.
- Database changes only through Alembic migrations (one migration per logical change, reversible). Never edit an applied migration.
- Add indexes deliberately and justify them in the migration or ADR.

## Security rules

- Passwords: argon2 hash; never store or log plaintext.
- JWT: short-lived access tokens (15 min), refresh tokens rotated and revocable, signature and expiry always verified, role checked server-side.
- Validate all input; parameterized queries only (SQLAlchemy does this, so never build SQL with f-strings).
- No secrets in git. `.env` is gitignored; K8s uses Secrets; AWS uses IAM roles with least privilege.
- Webhooks verify an HMAC signature.

## Testing requirements

- Unit tests for services (mock repositories). Integration tests against real Postgres/Redis (testcontainers or the compose stack).
- Test the unhappy paths: expired hold, double submit, invalid token, payment failure, Redis unavailable.
- Target ≥ 80% coverage on service logic. Tests must be deterministic (no sleeps; use fake clocks or short TTLs).
- A change is not done until `make lint typecheck test` passes.

## Docker & Kubernetes rules

- Multi-stage Dockerfiles, slim base, non-root user, no dev dependencies in the final image, `HEALTHCHECK` defined.
- K8s: every Deployment has resource requests/limits, liveness + readiness probes, and config from ConfigMap/Secret. HPA on CPU for `booking` and `events`. Migrations run as a Job, not at app startup.
- Manifests use Kustomize: `deploy/k8s/base` + `overlays/{local,aws}`.
- AWS target is **free tier only**: EC2 t3.micro with k3s (or Compose fallback), ECR, SQS, SES sandbox, CloudWatch. **Never** add EKS, NAT gateways, ALBs, ElastiCache or anything that incurs hourly cost without asking me first. Terraform must include a budget alert.

## Git & workflow

- Branch per task: `feat/…`, `fix/…`, `chore/…`. Conventional Commits (`feat(booking): add seat hold with redis lua`).
- Small, focused commits. Don't commit generated files, `.env`, or build artifacts.
- CI (`.github/workflows/ci.yml`) must stay green.

## How to work with me

1. **Work phase by phase** following the milestones in `docs/PRD.md` §9. Do not jump ahead.
2. **Plan before coding** for any non-trivial task: state the approach, the files you'll touch, and the tests you'll add. Wait for my go-ahead on large changes.
3. **One task at a time.** Finish it with tests, lint and types passing, then summarize what changed and what to verify.
4. When a design choice has trade-offs (locking strategy, schema, caching), **explain the trade-off briefly** and record it as an ADR in `docs/adr/`. I need to be able to explain every decision in an interview.
5. Explain non-obvious code as you write it. Prefer simple, readable solutions I can defend over clever ones.
6. If requirements are ambiguous or conflict with this file, **ask** instead of guessing.
7. If you spot a bug, race condition, or security issue in existing code, say so immediately, even if it's outside the current task.
8. Keep docs current: update README, `docs/`, `.env.example` and the Postman collection in the same change that alters behavior.

## Definition of done (per task)

- [ ] Implements the PRD requirement ID(s) referenced in the task
- [ ] Types, lint and tests pass (`make lint typecheck test`)
- [ ] Unhappy paths and (where relevant) concurrency tests added
- [ ] Migration added and reversible (if schema changed)
- [ ] `.env.example` and docs updated
- [ ] No new secrets, no hardcoded config

## Current phase

Phase 1 — Foundations: COMPLETED.
Phase 2 — Booking core: NEXT (Inventory, seat listing, holds with Redis Lua + DB locking, concurrency tests). Update this line as phases complete.
