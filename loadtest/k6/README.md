# TicketRush Concurrency & Flash Sale Load Testing

This test suite simulates high-concurrency ticket flash sales to validate zero overselling, deadlock avoidance, and token-bucket rate limiting.

## Flash Sale Scenario
- **Virtual Users**: 1,000 concurrent attendees.
- **Inventory**: Exactly 100 seats (5 rows of 20 seats).
- **Duration**: 30 seconds (ramping up to 1,000 VUs).
- **Concurrency Invariant**: Exactly 100 bookings confirmed, zero duplicate seats, zero overselling, zero HTTP 500 errors.

---

## Running the Benchmark

### Step 1: Ensure Full Local Stack Is Running
```bash
make up
# Or: docker compose up -d
```

### Step 2: Seed Test Data
Generates 1,000 test users with pre-signed JWT tokens, creates the flash-sale event (`status = 'on_sale'`), and generates 100 available seats:
```bash
uv run python loadtest/seed.py
```
This produces `loadtest/test_data.json` utilized by the k6 runner.

### Step 3: Execute k6 Flash Sale Concurrency Test
```bash
k6 run loadtest/k6/flash_sale.js
```

To run the cached catalog read benchmark:
```bash
k6 run loadtest/k6/browse.js
```

### Step 4: Verify Post-Run Invariants via SQL
Run the automated invariant verification script:
```bash
docker compose exec -T postgres psql -U ticketrush -d ticketrush < loadtest/verify_invariants.sql
```

Expected SQL output:
```
----------------------------------------------------------------------
Verifying Invariant 1: Total confirmed bookings must equal exactly 100
----------------------------------------------------------------------
 confirmed_bookings_count | status
--------------------------+--------
                      100 | PASS

----------------------------------------------------------------------
Verifying Invariant 2: Zero duplicate seats across confirmed bookings
----------------------------------------------------------------------
 seat_id | duplicates
---------+------------
(0 rows)

----------------------------------------------------------------------
Verifying Invariant 3: Exactly 100 seats marked "booked" in inventory
----------------------------------------------------------------------
 booked_seats_count | status
--------------------+--------
                100 | PASS
```
