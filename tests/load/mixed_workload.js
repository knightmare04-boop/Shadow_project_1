/*
 * "Test simultaneous users" (Module 9) — staged ramp across the mix a real
 * ERP day looks like: mostly browsing, some invoice submission, fewer
 * payments. Reports p50/p95/p99, throughput, and error rate at 50/200/500
 * concurrent virtual users, and — critically — WHERE it starts degrading,
 * which is the actual deliverable (not a pass/fail gate).
 *
 * Run:
 *   docker run --rm -i --add-host=host.docker.internal:host-gateway \
 *     -e API_BASE=http://host.docker.internal:8000 \
 *     grafana/k6 run - < tests/load/mixed_workload.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const API_BASE = __ENV.API_BASE || "http://localhost:8000";

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 50 },
        { duration: "1m", target: 50 },
        { duration: "30s", target: 200 },
        { duration: "1m", target: 200 },
        { duration: "30s", target: 500 },
        { duration: "1m", target: 500 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    // Not a hard gate that fails the build — recorded so the report can
    // quote exactly where reality diverged from the target, honestly.
    http_req_duration: ["p(95)<1000"],
    http_req_failed: ["rate<0.05"],
  },
};

const browseLatency = new Trend("browse_latency", true);
const writeLatency = new Trend("write_latency", true);
const errorRate = new Rate("errors");

export function setup() {
  const login = http.post(
    `${API_BASE}/api/v1/auth/login`,
    JSON.stringify({ email: "clerk@shadow-ledger.app", password: "devpassword123" }),
    { headers: { "Content-Type": "application/json" } },
  );
  return { token: login.json("access_token") };
}

export default function (data) {
  const headers = { Authorization: `Bearer ${data.token}`, "Content-Type": "application/json" };
  const roll = Math.random();

  if (roll < 0.7) {
    // 70%: browse (list vendors / invoices / payments — read-heavy, the
    // realistic majority of ERP traffic).
    const endpoint = ["vendors", "invoices", "payments"][Math.floor(Math.random() * 3)];
    const res = http.get(`${API_BASE}/api/v1/${endpoint}?limit=20`, { headers });
    browseLatency.add(res.timings.duration);
    errorRate.add(res.status >= 400);
    check(res, { "browse: 200": (r) => r.status === 200 });
  } else if (roll < 0.9) {
    // 20%: submit an invoice (write-heavy, exercises duplicate-detection queries).
    const res = http.get(`${API_BASE}/api/v1/vendors?limit=1`, { headers });
    const vendorId = res.json("0.id");
    if (vendorId) {
      const glList = http.get(`${API_BASE}/api/v1/gl-accounts`, { headers });
      const glId = glList.json("0.id");
      const inv = http.post(
        `${API_BASE}/api/v1/invoices`,
        JSON.stringify({
          invoice_number: `K6-LOAD-${__VU}-${__ITER}-${Date.now()}`, vendor_id: vendorId,
          invoice_date: "2026-09-15",
          lines: [{ line_no: 1, description: "k6 load", quantity: 1, unit_price: "50.00", gl_account_id: glId }],
        }),
        { headers },
      );
      writeLatency.add(inv.timings.duration);
      errorRate.add(inv.status >= 400);
    }
  } else {
    // 10%: alert queue (the forensic console's own read pattern).
    const res = http.get(`${API_BASE}/api/v1/alerts?limit=20`, { headers });
    browseLatency.add(res.timings.duration);
    errorRate.add(res.status >= 400);
  }

  sleep(Math.random() * 0.5 + 0.2); // think time — not a hammer test
}
