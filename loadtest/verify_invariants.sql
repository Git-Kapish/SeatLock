-- =============================================================================
-- TicketRush Invariant Verification Script
-- Run after the k6 flash-sale load test to guarantee zero oversells
-- =============================================================================

\echo '----------------------------------------------------------------------'
\echo 'Verifying Invariant 1: Total confirmed bookings must equal exactly 100'
\echo '----------------------------------------------------------------------'
SELECT
    COUNT(*) AS confirmed_bookings_count,
    CASE WHEN COUNT(*) = 100 THEN 'PASS' ELSE 'FAIL: Expected exactly 100' END AS status
FROM booking.bookings
WHERE status = 'confirmed';

\echo '----------------------------------------------------------------------'
\echo 'Verifying Invariant 2: Zero duplicate seats across confirmed bookings'
\echo '----------------------------------------------------------------------'
SELECT
    seat_id,
    COUNT(*) AS duplicates
FROM booking.booking_seats
WHERE status = 'confirmed'
GROUP BY seat_id
HAVING COUNT(*) > 1;

\echo '----------------------------------------------------------------------'
\echo 'Verifying Invariant 3: Exactly 100 seats marked "booked" in inventory'
\echo '----------------------------------------------------------------------'
SELECT
    COUNT(*) AS booked_seats_count,
    CASE WHEN COUNT(*) = 100 THEN 'PASS' ELSE 'FAIL: Expected exactly 100' END AS status
FROM booking.seats
WHERE status = 'booked';

\echo '----------------------------------------------------------------------'
\echo 'Verifying Invariant 4: No seats in invalid states'
\echo '----------------------------------------------------------------------'
SELECT
    status,
    COUNT(*) AS count
FROM booking.seats
GROUP BY status;

\echo '----------------------------------------------------------------------'
\echo 'Verifying Invariant 5: Processed webhooks count equals confirmed bookings'
\echo '----------------------------------------------------------------------'
SELECT
    COUNT(*) AS processed_webhooks_count,
    CASE WHEN COUNT(*) = 100 THEN 'PASS' ELSE 'FAIL: Expected 100' END AS status
FROM booking.processed_webhooks;
