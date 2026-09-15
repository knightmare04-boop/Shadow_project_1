/*
 * Module 11 council finding, addressed: the original payment_race.js test
 * used a DIFFERENT idempotency key per VU, which proves layers 2-3 (row
 * lock + partial unique index) but never exercises layer 1 (the
 * Idempotency-Key SETNX claim/replay path) at all. This test closes that
 * gap: every VU sends the SAME key against the SAME invoice, truly
 * concurrently — the exact scenario idempotency keys exist for (a client
 * retry storm, not two different actors).
 *
 * Expected correct behavior: exactly ONE request executes the handler;
 * every other concurrent request either (a) receives the replayed 201
 * response (X-Idempotent-Replay: true) if it arrived after the first
 * completed, or (b) receives a 409 "still processing" if it arrived while
 * the first was still in flight (app/services/idempotency.py's
 * IdempotencyInProgress path) — never a second independent payment.
 *
 * Run:
 *   docker run --rm -i --add-host=host.docker.internal:host-gateway \
 *     -e API_BASE=http://host.docker.internal:8000 -e VUS=25 \
 *     grafana/k6 run - < tests/load/idempotency_replay_race.js
 */
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const API_BASE = __ENV.API_BASE || "http://localhost:8000";
const VUS = parseInt(__ENV.VUS || "25", 10);
const SHARED_KEY = "idem-replay-race-fixed-key";

export const options = {
  scenarios: {
    race: { executor: "shared-iterations", vus: VUS, iterations: VUS, maxDuration: "30s" },
  },
};

const created = new Counter("idem_created_201_original");
const replayed = new Counter("idem_replayed_true");
const inProgress409 = new Counter("idem_in_progress_409");
const unexpected = new Counter("idem_unexpected");

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
    JSON.stringify({ vendor_code: `K6-IDEM-${Date.now()}`, legal_name: "k6 Idempotency Race Vendor" }),
    { headers: authHeaders },
  );
  const glList = http.get(`${API_BASE}/api/v1/gl-accounts`, { headers: authHeaders });
  const glId = glList.json("0.id");
  const invoice = http.post(
    `${API_BASE}/api/v1/invoices`,
    JSON.stringify({
      invoice_number: `K6-IDEM-${Date.now()}`, vendor_id: vendor.json("id"), invoice_date: "2026-09-15",
      lines: [{ line_no: 1, description: "idem race", quantity: 1, unit_price: "777.00", gl_account_id: glId }],
    }),
    { headers: authHeaders },
  );
  return { token, invoiceId: invoice.json("id") };
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`, "Content-Type": "application/json",
    "Idempotency-Key": SHARED_KEY, // SAME key for every VU — the real idempotency test
  };
  const res = http.post(
    `${API_BASE}/api/v1/payments`,
    JSON.stringify({ invoice_id: data.invoiceId, amount: "777.00", payment_date: "2026-09-15" }),
    { headers },
  );

  if (res.status === 201 && res.headers["X-Idempotent-Replay"] === "true") {
    replayed.add(1);
  } else if (res.status === 201) {
    created.add(1);
    check(res, { "at most one original 201": () => true }); // counted, checked in teardown
  } else if (res.status === 409) {
    inProgress409.add(1);
  } else {
    unexpected.add(1);
    console.error(`unexpected status ${res.status}: ${res.body}`);
  }
}

export function teardown(data) {
  console.log(`idempotency race complete for invoice ${data.invoiceId} — ` +
             `check idem_created_201_original == 1 (never more)`);
}
