import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const browseDuration = new Trend('browse_duration_ms');
const successfulReads = new Counter('successful_reads_count');

export const options = {
  stages: [
    { duration: '5s', target: 100 },
    { duration: '15s', target: 500 },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<100'], // 95% of cached reads under 100ms
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.GATEWAY_URL || 'http://localhost:8000';

export default function () {
  // 1. Browse event listing (cache-aside)
  const listStart = Date.now();
  const listRes = http.get(`${BASE_URL}/api/v1/events?limit=20`);
  browseDuration.add(Date.now() - listStart);

  check(listRes, {
    'list events status is 200': (r) => r.status === 200,
  });

  if (listRes.status === 200) {
    successfulReads.add(1);
    const body = listRes.json();
    const items = body.items || [];
    if (items.length > 0) {
      const eventId = items[0].id;
      // 2. Fetch specific event details (cache-aside)
      const detailRes = http.get(`${BASE_URL}/api/v1/events/${eventId}`);
      check(detailRes, {
        'get event status is 200': (r) => r.status === 200,
      });
      if (detailRes.status === 200) {
        successfulReads.add(1);
      }
    }
  }

  sleep(0.05 + Math.random() * 0.1);
}
