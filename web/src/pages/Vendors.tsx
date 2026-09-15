import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, toApiError } from "../lib/api";
import type { Vendor } from "../types/api";
import { SkeletonRows, EmptyState, ErrorState } from "../components/States";
import { ErrorBoundary } from "../components/ErrorBoundary";

function useVendors() {
  return useQuery({
    queryKey: ["vendors"],
    queryFn: async () => (await api.get<Vendor[]>("/api/v1/vendors")).data,
  });
}

function NewVendorForm({ onCreated }: { onCreated: () => void }) {
  const [vendorCode, setVendorCode] = useState("");
  const [legalName, setLegalName] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () =>
      (await api.post<Vendor>("/api/v1/vendors", { vendor_code: vendorCode, legal_name: legalName })).data,
    onSuccess: () => {
      setVendorCode("");
      setLegalName("");
      setFieldErrors({});
      setFormError(null);
      onCreated();
    },
    onError: (err) => {
      const apiErr = toApiError(err);
      if (apiErr.fieldErrors.length) {
        setFieldErrors(Object.fromEntries(apiErr.fieldErrors.map((f) => [f.field, f.message])));
      } else {
        setFormError(apiErr.message);
      }
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    mutation.mutate();
  }

  return (
    <form onSubmit={onSubmit} className="panel">
      <h2>New Vendor</h2>
      <div className="panel-body">
        <div className="row" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 160px" }}>
            <label htmlFor="vendor_code">Vendor code</label>
            <input id="vendor_code" required value={vendorCode}
                   onChange={(e) => setVendorCode(e.target.value)} />
            {fieldErrors.vendor_code && <div className="field-error">{fieldErrors.vendor_code}</div>}
          </div>
          <div className="field" style={{ flex: "2 1 260px" }}>
            <label htmlFor="legal_name">Legal name</label>
            <input id="legal_name" required value={legalName}
                   onChange={(e) => setLegalName(e.target.value)} />
            {fieldErrors.legal_name && <div className="field-error">{fieldErrors.legal_name}</div>}
          </div>
          <div className="field" style={{ flex: "0 0 auto", paddingTop: "1.2rem" }}>
            <button type="submit" className="primary" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create vendor"}
            </button>
          </div>
        </div>
        {formError && <div className="field-error" role="alert">{formError}</div>}
      </div>
    </form>
  );
}

function VendorTable() {
  const { data, isLoading, isError, error, refetch } = useVendors();

  if (isLoading) {
    return (
      <div className="panel">
        <h2>Vendors</h2>
        <div className="panel-body"><SkeletonRows rows={5} cols={4} /></div>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="panel">
        <h2>Vendors</h2>
        <ErrorState message={toApiError(error).message} correlationId={toApiError(error).correlationId}
                    onRetry={() => refetch()} />
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="panel">
        <h2>Vendors</h2>
        <EmptyState icon="📇" title="No vendors yet" hint="Create your first vendor using the form above." />
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Vendors ({data.length})</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr><th>Code</th><th>Legal name</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody>
            {data.map((v) => (
              <tr key={v.id}>
                <td className="mono">{v.vendor_code}</td>
                <td>{v.legal_name}</td>
                <td>
                  {v.is_blocked
                    ? <span className="badge warn">blocked</span>
                    : <span className="badge ok">active</span>}
                </td>
                <td className="sub">{new Date(v.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Vendors() {
  const queryClient = useQueryClient();
  return (
    <div className="stack">
      <h1>Vendors</h1>
      <ErrorBoundary panelName="New vendor form">
        <NewVendorForm onCreated={() => queryClient.invalidateQueries({ queryKey: ["vendors"] })} />
      </ErrorBoundary>
      <ErrorBoundary panelName="Vendor list">
        <VendorTable />
      </ErrorBoundary>
    </div>
  );
}
