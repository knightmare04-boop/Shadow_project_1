import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, newIdempotencyKey, toApiError } from "../lib/api";
import type { Invoice, Payment } from "../types/api";
import { SkeletonRows, EmptyState, ErrorState } from "../components/States";
import { ErrorBoundary } from "../components/ErrorBoundary";

function usePayments() {
  return useQuery({
    queryKey: ["payments"],
    queryFn: async () => (await api.get<Payment[]>("/api/v1/payments")).data,
  });
}
function useUnpaidInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: async () => (await api.get<Invoice[]>("/api/v1/invoices")).data,
    select: (invoices) => invoices.filter((i) => i.status !== "paid" && i.status !== "voided"),
  });
}

function NewPaymentForm({ invoices, onCreated }: { invoices: Invoice[]; onCreated: () => void }) {
  const [invoiceId, setInvoiceId] = useState(invoices[0]?.id ?? "");
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<string | null>(null);

  const selected = invoices.find((i) => i.id === invoiceId);

  const mutation = useMutation({
    mutationFn: async () => {
      // A fresh key per submit attempt — the SAME key is only reused by the
      // browser's own retry logic within one logical click, never
      // generated twice for two different user actions. This is what
      // "prevent duplicate submissions" means at the client: a double-
      // click sends two requests, but a real network retry of the SAME
      // request reuses the key that request already committed to.
      const key = newIdempotencyKey();
      return (
        await api.post<Payment>(
          "/api/v1/payments",
          { invoice_id: invoiceId, amount: selected?.total_amount, payment_date: paymentDate },
          { headers: { "Idempotency-Key": key } },
        )
      ).data;
    },
    onSuccess: () => {
      setError(null);
      setErrorType(null);
      onCreated();
    },
    onError: (err) => {
      const apiErr = toApiError(err);
      setError(apiErr.message);
      setErrorType(apiErr.errorType);
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  if (invoices.length === 0) {
    return (
      <div className="panel">
        <h2>Post Payment</h2>
        <EmptyState title="No unpaid invoices" hint="Every submitted invoice has already been paid, or none exist yet." />
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="panel">
      <h2>Post Payment</h2>
      <div className="panel-body stack">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 260px" }}>
            <label htmlFor="invoice">Invoice</label>
            <select id="invoice" value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)}>
              {invoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.invoice_number} — ${Number(i.total_amount).toLocaleString()}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 160px" }}>
            <label htmlFor="payment_date">Payment date</label>
            <input id="payment_date" type="date" required value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
          </div>
          <div className="field" style={{ flex: "0 0 auto", paddingTop: "1.2rem" }}>
            <button type="submit" className="primary" disabled={mutation.isPending}>
              {mutation.isPending ? "Posting…" : "Post payment"}
            </button>
          </div>
        </div>
        {error && (
          <div className="field-error" role="alert">
            {errorType === "duplicate_payment" ? "This invoice already has a payment in progress or settled. " : ""}
            {error}
          </div>
        )}
      </div>
    </form>
  );
}

function PaymentTable() {
  const { data, isLoading, isError, error, refetch } = usePayments();

  if (isLoading) return <div className="panel"><h2>Payments</h2><div className="panel-body"><SkeletonRows rows={5} cols={4} /></div></div>;
  if (isError) {
    return (
      <div className="panel"><h2>Payments</h2>
        <ErrorState message={toApiError(error).message} correlationId={toApiError(error).correlationId} onRetry={() => refetch()} />
      </div>
    );
  }
  if (!data || data.length === 0) {
    return <div className="panel"><h2>Payments</h2><EmptyState icon="💸" title="No payments posted yet" /></div>;
  }

  const STATUS_CLS: Record<string, string> = { posted: "ok", cleared: "ok", pending: "", failed: "warn", voided: "warn" };
  return (
    <div className="panel">
      <h2>Payments ({data.length})</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th>Amount</th><th>Status</th><th>Date</th><th>Created</th></tr></thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id}>
                <td>${Number(p.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                <td><span className={`badge ${STATUS_CLS[p.status] ?? ""}`}>{p.status}</span></td>
                <td className="sub">{p.payment_date}</td>
                <td className="sub">{new Date(p.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Payments() {
  const queryClient = useQueryClient();
  const { data: invoices } = useUnpaidInvoices();

  function onCreated() {
    queryClient.invalidateQueries({ queryKey: ["payments"] });
    queryClient.invalidateQueries({ queryKey: ["invoices"] });
  }

  return (
    <div className="stack">
      <h1>Payments</h1>
      <p className="sub">Every payment is fraud-scored live on posting — check the Alert Queue for anything flagged.</p>
      <ErrorBoundary panelName="New payment form">
        <NewPaymentForm invoices={invoices ?? []} onCreated={onCreated} />
      </ErrorBoundary>
      <ErrorBoundary panelName="Payment list">
        <PaymentTable />
      </ErrorBoundary>
    </div>
  );
}
