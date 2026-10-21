# ADR 0001: Monorepo Architecture with Shared Common Library

## Status
Accepted

## Context
TicketRush comprises three independent microservices (`auth`, `events`, `booking`) plus a background worker (`notifier`). Managing three completely separate repositories would introduce friction in local orchestration, cross-cutting updates (such as auth token verification and structured logging), and continuous integration tooling.

## Decision
We adopted a **monorepo** layout backed by `uv` workspaces:
- A shared `libs/common/` package (`ticketrush_common`) encapsulating cross-cutting logging, error hierarchies, JWT security, and SQS/Redis client managers.
- `libs/common` contains zero business domain logic and never imports from any service.
- Each service in `services/*` and worker in `workers/*` maintains its own `pyproject.toml`, Dockerfile, Alembic migrations, and test suite.

## Consequences
- **Positive**: Single `docker compose up`, atomic cross-service PRs, unified CI pipeline, zero duplicated boilerplate.
- **Negative**: Monorepo tooling required to prevent accidental circular imports across services.
