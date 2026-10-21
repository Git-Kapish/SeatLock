# ADR 0003: Database Isolation via PostgreSQL Schemas

## Status
Accepted

## Context
Microservices require strict data ownership to prevent tight coupling and schema contamination. Running separate PostgreSQL database servers per service in local development increases memory overhead and operational complexity.

## Decision
We utilize a single PostgreSQL cluster with strict **PostgreSQL schema isolation**:
- `auth`: Owns users, credentials, refresh tokens.
- `events`: Owns events, venues, capacities.
- `booking`: Owns seats, holds, bookings, payments, idempotency keys, processed webhooks.

Cross-schema foreign keys and direct SQL queries between services are strictly prohibited. Inter-service data sharing occurs exclusively via HTTP APIs or SQS events.

## Consequences
- **Positive**: Low local resource footprint; strict service autonomy; straightforward future split into separate RDS instances.
- **Negative**: Requires discipline and code reviews to avoid accidental cross-schema querying in repositories.
