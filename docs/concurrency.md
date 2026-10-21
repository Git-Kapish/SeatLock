# TicketRush — Concurrency & Correctness Model

Preventing overselling under high concurrency is the primary technical objective of TicketRush. This document explains the exact locking mechanics, algorithms, and invariants that guarantee zero double-bookings.

---

## 1. The Flash Sale Concurrency Challenge

During flash sales, thousands of users compete for a limited number of high-demand seats within milliseconds:
- **Race Condition**: Two users read a seat as `available` at timestamp $t_0$, and both attempt to write a booking at $t_1$.
- **Partial Allocation Failure**: A user requests 4 seats together; if only 3 are acquired, the user must receive nothing rather than an orphaned partial hold.
- **Database Deadlocks**: Concurrent transactions acquiring seats in different orders (Transaction A locks Seat 1 then Seat 2; Transaction B locks Seat 2 then Seat 1) produce database deadlock exceptions.
- **Zombie Holds**: Abandoned checkout sessions leaving seats locked permanently.

---

## 2. The Two-Tier Concurrency Architecture

TicketRush uses a **two-tier defense-in-depth locking mechanism**:

```mermaid
flowchart TD
    Req[Hold Request for Seats A & B] --> Step1[Tier 1: Atomic Redis Lua Script]
    Step1 -->|Any Key Taken| Abort1[Return 409 SEAT_UNAVAILABLE<br/>Zero Keys Acquired]
    Step1 -->|All Keys Free| Step2[All Redis Keys Locked for 10 min]
    Step2 --> Step3[Tier 2: Postgres Transaction]
    Step3 --> Step4[SELECT ... FOR UPDATE<br/>ORDER BY seat_id ASC]
    Step4 -->|Any Seat Not Available| Rollback[Rollback DB Transaction<br/>Release Redis Keys via Lua<br/>Return 409]
    Step4 -->|All Seats Available| Commit[UPDATE seats SET status='held'<br/>INSERT INTO holds & hold_seats<br/>Commit DB Transaction<br/>Return 201 Created]
```

### Tier 1: Redis Lua Atomic Hold Acquisition
Redis executes Lua scripts atomically in a single thread, guaranteeing zero race conditions between inspection and acquisition.

```lua
-- File: services/booking/app/redis_scripts/acquire_holds.lua
local event_id = ARGV[1]
local user_id = ARGV[2]
local ttl = tonumber(ARGV[3])

-- Step 1: All-or-nothing check. If ANY seat is taken, abort immediately.
for i = 1, #KEYS do
    if redis.call('EXISTS', KEYS[i]) == 1 then
        return 0
    end
end

-- Step 2: All seats are free. Acquire all keys atomically.
for i = 1, #KEYS do
    redis.call('SET', KEYS[i], user_id, 'EX', ttl)
end

return 1
```

### Tier 2: PostgreSQL Row-Level Locking with Deadlock Prevention
PostgreSQL is the authoritative source of truth. Even if Redis is empty or restarted, PostgreSQL row locks prevent double allocation.

To eliminate deadlocks completely, TicketRush enforces **lexicographical ordering of resource locks**:

```python
# services/booking/app/repositories/seat_repository.py
stmt = (
    select(Seat)
    .where(
        Seat.event_id == event_id,
        Seat.id.in_(seat_ids),
    )
    .order_by(Seat.id.asc())  # <--- CRUCIAL: Breaks the Coffman circular wait condition
    .with_for_update()
)
```

By acquiring locks strictly in ascending order of `seat_id`, circular lock waiting is mathematically impossible.

---

## 3. Database Invariant Constraints

Application logic is backed by PostgreSQL relational constraints:

```sql
-- Partial unique index: A seat can belong to only one active booking
CREATE UNIQUE INDEX ix_booking_seats_active
ON booking.booking_seats (seat_id)
WHERE status IN ('pending_payment', 'confirmed');
```

If any software bug were to attempt creating a duplicate active booking for the same seat, PostgreSQL immediately rejects the transaction with an integrity violation (`23505 unique_violation`).

---

## 4. Hold Expiration & Background Reconciliation

1. **TTL Expiration**: Redis keys automatically expire after 10 minutes (`600 seconds`).
2. **Periodic Sweeper**: The `notifier` worker executes a reconciliation sweep every 30 seconds:
   ```sql
   SELECT * FROM booking.holds
   WHERE status = 'active' AND expires_at <= NOW();
   ```
   For each expired hold:
   - Marks hold as `'expired'`.
   - Returns held seats to `'available'` and increments `version`.
   - Deletes any lingering Redis hold keys.

---

## 5. Verification Results

In automated stress tests simulating 50 concurrent virtual users triggered at the exact same millisecond for the exact same seat:
- **Successes (201 Created)**: Exactly 1
- **Conflicts (409 Conflict)**: Exactly 49
- **Database Double Bookings**: Exactly 0
- **Execution Time**: 0.03 seconds
