# ADR 0002: Atomic Seat Holds via Redis Lua Scripts

## Status
Accepted

## Context
During ticket flash sales, thousands of users request seat reservations concurrently. Relying exclusively on PostgreSQL row locks under high load risks database connection pool saturation, lock contention, and thread starvation. Conversely, multi-step Redis operations (`GET` then `SET`) suffer from race conditions.

## Decision
We implemented a **two-tier locking strategy**:
1. **Tier 1 (Redis Lua)**: All-or-nothing hold acquisition using an atomic Lua script (`acquire_holds.lua`). If any key in the requested batch is already taken, the script aborts immediately without acquiring any locks.
2. **Tier 2 (PostgreSQL)**: Authoritative seat status updates inside a transaction using `SELECT ... FOR UPDATE ORDER BY seat_id ASC`.

## Consequences
- **Positive**: Sub-millisecond rejection of competing requests without touching PostgreSQL; zero deadlocks guaranteed by lexicographical sorting.
- **Negative**: Requires maintaining Lua scripts and ensuring Redis lock keys match database state upon transaction rollback.
