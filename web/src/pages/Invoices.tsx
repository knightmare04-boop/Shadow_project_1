import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, toApiError } from "../lib/api";
import type { Invoice, Vendor } from "../types/api";
import { SkeletonRows, EmptyState, ErrorState } from "../components/States";
import { ErrorBoundary } from "../components/ErrorBoundary";

function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: async () => (await api.get<Invoice[]>("/api/v1/invoices")).data,
  });
}
function useVendorsForSelect() {
  return useQuery({
    queryKey: ["vendors"],
    queryFn: async () => (await api.get<Vendor[]>("/api/v1/vendors")).data,
  });
}

const DUP_LABEL: Record<string, { label: string; cls: string }> = {
  clear: { label: "clear", cls: "ok" },
  flagged_near_duplicate: { label: "possible duplicate", cls: "warn" },
  reviewed_cleared: { label: "reviewed: cleared", cls: "ok" },
  reviewed_confirmed_duplicate: { label: "confirmed duplicate", cls: "warn" },
};

function NewInvoiceForm({ vendors, onCreated }: { vendors: Vendor[]; onCreated: () => void }) {
  const [vendorId, setVendorId] = useState(vendors[0]?.id ?? "");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unitPrice, setUnitPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  // A GL account is required per line; in a fuller build this would be a
  // proper picker fed by GET /api/v1/gl-accounts — using a fixed default
  // here (Office Supplies Expense, seeded by tools/seed_core.py) keeps this
  // form usable without that endpoint existing yet.
  const mutation = useMutation({
    mutationFn: async () => {
      const glRes = await api.get<{ id: string }[]>("/api/v1/gl-accounts").catch(() => ({ data: [] }));
      const glAccountId = glRes.data[0]?.id;
      return (
        await api.post<Invoice>("/api/v1/invoices", {
          invoice_number: invoiceNumber,
          vendor_id: vendorId,
          invoice_date: invoiceDate,
          lines: [{ line_no: 1, description, quantity: Number(quantity), unit_price: unitPrice, gl_account_id: glAccountId }],
        })
      ).data;
    },
    onSuccess: () => {
      setInvoiceNumber("");
      setDescription("");
      setUnitPrice("");
      setError(null);
      onCreated();
    },
    onError: (err) => setError(toApiError(err).message),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  if (vendors.length === 0) {
    return (
      <div className="panel">
        <h2>New Invoice</h2>
        <EmptyState title="No vendors to invoice" hint="Create a vendor first on the Vendors page." />
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="panel">
      <h2>New Invoice</h2>
      <div className="panel-body stack">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 200px" }}>
            <label htmlFor="vendor">Vendor</label>
            <select id="vendor" value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
              {vendors.map((v) => <option key={v.id} value={v.id}>{v.vendor_code} — {v.legal_name}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 160px" }}>
            <label htmlFor="invoice_number">Invoice number</label>
            <input id="invoice_number" required value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
          </div>
          <div className="field" style={{ flex: "1 1 140px" }}>
            <label htmlFor="invoice_date">Invoice date</label>
            <input id="invoice_date" type="date" required value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
          </div>
        </div>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "2 1 220px" }}>
            <label htmlFor="description">Line description</label>
            <input id="description" required value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="field" style={{ flex: "0 1 100px" }}>
            <label htmlFor="quantity">Qty</label>
            <input id="quantity" type="number" min="0.01" step="0.01" required value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </div>
          <div className="field" style={{ flex: "0 1 140px" }}>
            <label htmlFor="unit_price">Unit price</label>
            <input id="unit_price" type="number" min="0.01" step="0.01" required value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} />
          </div>
          <div className="field" style={{ flex: "0 0 auto", paddingTop: "1.2rem" }}>
            <button type="submit" className="primary" disabled={mutation.isPending}>
              {mutation.isPending ? "Submitting…" : "Submit invoice"}
            </button>
          </div>
        </div>
        {error && <div className="field-error" role="alert">{error}</div>}
      </div>
    </form>
  );
}

function InvoiceTable() {
  const { data, isLoading, isError, error, refetch } = useInvoices();

  if (isLoading) {
    return <div className="panel"><h2>Invoices</h2><div className="panel-body"><SkeletonRows rows={5} cols={5} /></div></div>;
  }
  if (isError) {
    return (
      <div className="panel"><h2>Invoices</h2>
        <ErrorState message={toApiError(error).message} correlationId={toApiError(error).correlationId} onRetry={() => refetch()} />
      </div>
    );
  }
  if (!data || data.length === 0) {
    return <div className="panel"><h2>Invoices</h2><EmptyState icon="🧾" title="No invoices yet" hint="Submit one using the form above." /></div>;
  }

  return (
    <div className="panel">
      <h2>Invoices ({data.length})</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th>Number</th><th>Amount</th><th>Status</th><th>Duplicate check</th><th>Date</th></tr></thead>
          <tbody>
            {data.map((inv) => {
              const dup = DUP_LABEL[inv.duplicate_check_status] ?? { label: inv.duplicate_check_status, cls: "" };
              return (
                <tr key={inv.id}>
                  <td className="mono">{inv.invoice_number}</td>
                  <td>${Number(inv.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  <td><span className="badge">{inv.status.replace("_", " ")}</span></td>
                  <td><span className={`badge ${dup.cls}`}>{dup.label}</span></td>
                  <td className="sub">{inv.invoice_date}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Invoices() {
  const queryClient = useQueryClient();
  const { data: vendors } = useVendorsForSelect();

  return (
    <div className="stack">
      <h1>Invoices</h1>
      <ErrorBoundary panelName="New invoice form">
        <NewInvoiceForm vendors={vendors ?? []} onCreated={() => queryClient.invalidateQueries({ queryKey: ["invoices"] })} />
      </ErrorBoundary>
      <ErrorBoundary panelName="Invoice list">
        <InvoiceTable />
      </ErrorBoundary>
    </div>
  );
}
