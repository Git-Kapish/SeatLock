import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import crypto from 'k6/crypto';

// Custom Metrics
const successfulHolds = new Counter('successful_holds_count');
const successfulBookings = new Counter('successful_bookings_count');
const successfulPayments = new Counter('successful_payments_count');
const seatConflicts = new Counter('seat_conflicts_409_count');
const rateLimits = new Counter('rate_limited_429_count');
const serverErrors = new Counter('server_errors_500_count');
const holdDuration = new Trend('hold_request_duration_ms');

// Load seeded test data if available, or fall back to mock data
let testData;
try {
  testData = JSON.parse(open('../test_data.json'));
} catch (e) {
  testData = {
    event_id: '00000000-0000-0000-0000-000000000001',
    seat_ids: Array.from({ length: 100 }, (_, i) => `00000000-0000-0000-0000-${String(i + 1).padStart(12, '0')}`),
    users: Array.from({ length: 1000 }, (_, i) => ({
      user_id: `user-${i + 1}`,
      token: 'mock-jwt-token',
    })),
    webhook_secret: 'development-payment-webhook-secret-key-min-32-chars',
  };
}

export const options = {
  scenarios: {
    flash_sale: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '3s', target: 200 },    // Initial surge
        { duration: '5s', target: 1000 },   // 1,000 concurrent users competing for 100 seats
        { duration: '15s', target: 1000 },  // High load persistence
        { duration: '5s', target: 0 },      // Ramp down
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    'http_req_duration{type:hold}': ['p(95)<300'], // 95% of hold requests under 300ms
    'server_errors_500_count': ['count==0'],       // Zero 500 errors allowed
  },
};

const BASE_URL = __ENV.GATEWAY_URL || 'http://localhost:8000';

function randomUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function () {
  const vuIndex = (__VU - 1) % testData.users.length;
  const user = testData.users[vuIndex];
  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${user.token}`,
  };

  // 1. Pick a random seat to compete for
  const randomSeatIndex = Math.floor(Math.random() * testData.seat_ids.length);
  const targetSeatId = testData.seat_ids[randomSeatIndex];

  // 2. Attempt atomic seat hold
  const holdPayload = JSON.stringify({
    event_id: testData.event_id,
    seat_ids: [targetSeatId],
  });

  const holdStart = Date.now();
  const holdRes = http.post(
    `${BASE_URL}/api/v1/booking/holds`,
    holdPayload,
    { headers: authHeaders, tags: { type: 'hold' } }
  );
  holdDuration.add(Date.now() - holdStart);

  if (holdRes.status === 201) {
    successfulHolds.add(1);
    const holdData = holdRes.json();
    const holdId = holdData.id;

    // 3. Convert hold to booking with idempotency key
    const idempotencyKey = randomUUID();
    const bookingPayload = JSON.stringify({ hold_id: holdId });
    const bookingRes = http.post(
      `${BASE_URL}/api/v1/booking/bookings`,
      bookingPayload,
      {
        headers: Object.assign({}, authHeaders, { 'Idempotency-Key': idempotencyKey }),
        tags: { type: 'booking' },
      }
    );

    if (bookingRes.status === 201) {
      successfulBookings.add(1);
      const bookingData = bookingRes.json();
      const bookingId = bookingData.id;

      // 4. Simulate payment gateway webhook
      const webhookPayload = JSON.stringify({
        event_id: randomUUID(),
        event_type: 'payment.succeeded',
        occurred_at: new Date().toISOString(),
        data: {
          booking_id: bookingId,
          amount_cents: bookingData.total_cents,
        },
      });

      const signature = crypto.hmac('sha256', testData.webhook_secret, webhookPayload, 'hex');
      const webhookRes = http.post(
        `${BASE_URL}/api/v1/booking/payments/webhook`,
        webhookPayload,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Signature-256': signature,
          },
          tags: { type: 'webhook' },
        }
      );

      if (webhookRes.status === 200) {
        successfulPayments.add(1);
      }
    }
  } else if (holdRes.status === 409) {
    // Expected concurrency conflict: seat was locked by another user
    seatConflicts.add(1);
  } else if (holdRes.status === 429) {
    // Rate limit hit
    rateLimits.add(1);
  } else if (holdRes.status >= 500) {
    serverErrors.add(1);
  }

  // Small random think time between retry cycles
  sleep(0.1 + Math.random() * 0.2);
}
