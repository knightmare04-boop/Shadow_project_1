/*
 * The duplicate-payment race, formalized as a k6 test (Module 9). This is
 * the automated, repeatable version of the manual curl-based proof from
 * Module 4: N virtual users fire truly concurrent payment requests at the
 * SAME invoice, each with a DIFFERENT idempotency key (simulating N
 * independent actors, not N retries of one request — retries are already
 * covered by the idempotency-key replay test). Exactly one must succeed.
 *
 * Run (from repo root, API already running on the host):
 *   docker run --rm -i --add-host=host.docker.internal:host-gateway \
 *     -e API_BASE=http://host.docker.internal:8000 -e VUS=50 \
 *     grafana/k6 run - < tests/load/payment_race.js
 */
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const API_BASE = __ENV.API_BASE || "http://localhost:8000";
const VUS = parseInt(__ENV.VUS || "20", 10);

export const options = {
  scenarios: {
    race: {
      executor: "shared-iterations",
      vus: VUS,
      iterations: VUS,
      maxDuration: "30s",
    },
  },
};

const successCount = new Counter("payment_race_success");
const duplicateRejectedCount = new Counter("payment_race_duplicate_rejected");
const unexpectedCount = new Counter("payment_race_unexpected");

// Setup runs ONCE (not per-VU): log in, create one vendor + invoice, and
// hand every VU the SAME invoice_id — that shared target is the whole point.
export function setup() {
  const login = http.post(
    `${API_BASE}/api/v1/auth/login`,
    JSON.stringify({ email: "clerk@shadow-ledger.app", password: "devpassword123" }),
    { headers: { "Content-Type": "application/json" } },
  );
  const token = login.json("access_token");
  const authHeaders = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const vendor = http.post(
    `${API_BASE}/api/v1/vendors`,
    JSON.stringify({ vendor_code: `K6-RACE-${Date.now()}`, legal_name: "k6 Race Test Vendor" }),
    { headers: authHeaders },
  );
  const vendorId = vendor.json("id");

  const glList = http.get(`${API_BASE}/api/v1/gl-accounts`, { headers: authHeaders });
  const glId = glList.json("0.id");

  const invoice = http.post(
    `${API_BASE}/api/v1/invoices`,
    JSON.stringify({
      invoice_number: `K6-RACE-${Date.now()}`, vendor_id: vendorId, invoice_date: "2026-09-15",
      lines: [{ line_no: 1, description: "k6 race test", quantity: 1, unit_price: "999.00", gl_account_id: glId }],
    }),
    { headers: authHeaders },
  );

  return { token, invoiceId: invoice.json("id") };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
    "Idempotency-Key": `k6-race-${__VU}-${__ITER}-${Date.now()}`, // DIFFERENT key per VU — the actual race
  };
  const res = http.post(
    `${API_BASE}/api/v1/payments`,
    JSON.stringify({ invoice_id: data.invoiceId, amount: "999.00", payment_date: "2026-09-15" }),
    { headers },
  );

  if (res.status === 201) {
    successCount.add(1);
  } else if (res.status === 409) {
    duplicateRejectedCount.add(1);
    check(res, { "409 body names duplicate_payment": (r) => r.json("type") && r.json("type").includes("duplicate_payment") });
  } else {
    unexpectedCount.add(1);
    console.error(`unexpected status ${res.status}: ${res.body}`);
  }
}

export function teardown(data) {
  console.log(`race complete for invoice ${data.invoiceId} — check payment_race_success == 1`);
}
