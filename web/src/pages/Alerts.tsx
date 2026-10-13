import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, toApiError } from "../lib/api";
import type { Alert } from "../types/api";
import { SkeletonRows, EmptyState, InlineSpinner } from "../components/States";
import { ErrorBoundary } from "../components/ErrorBoundary";

function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: async () => (await api.get<Alert[]>("/api/v1/alerts")).data,
    refetchInterval: 15_000, // the queue should feel live without a manual refresh
  });
}

const FEEDBACK_LABEL: Record<string, { label: string; cls: string }> = {
  open: { label: "awaiting review", cls: "" },
  confirmed_fraud: { label: "confirmed fraud", cls: "warn" },
  false_positive: { label: "false positive", cls: "ok" },
  escalated: { label: "escalated", cls: "warn" },
};

/** SHAP waterfall — a horizontal bar per driver, signed by push direction,
 * width scaled to |shap|. No charting library needed for 5 bars. */
function ShapWaterfall({ drivers }: { drivers: Alert["risk_drivers"] }) {
  if (drivers.length === 0) return <p className="sub">No driver breakdown available for this alert.</p>;
  const maxAbs = Math.max(...drivers.map((d) => Math.abs(d.shap)), 0.0001);
  return (
    <div className="stack" style={{ gap: "0.5rem" }}>
      {drivers.map((d) => {
        const pct = (Math.abs(d.shap) / maxAbs) * 100;
        const pushesUp = d.shap >= 0;
        return (
          <div key={d.feature}>
            <div className="row between" style={{ fontSize: "0.78rem" }}>
              <span className="mono">{d.feature}</span>
              <span className="sub">value: {d.value ?? "—"} · shap: {d.shap.toFixed(3)}</span>
            </div>
            <div style={{ height: 8, background: "var(--line)", borderRadius: 4, position: "relative" }}>
              <div style={{
                position: "absolute", top: 0, bottom: 0,
                [pushesUp ? "left" : "right"]: "50%",
                width: `${pct / 2}%`,
                background: pushesUp ? "var(--alert)" : "var(--accent)",
                borderRadius: 4,
              }} />
              <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "var(--ink)", opacity: 0.4 }} />
            </div>
          </div>
        );
      })}
      <p className="sub" style={{ fontSize: "0.72rem" }}>
        <span style={{ color: "var(--alert)" }}>■</span> pushes risk up ·{" "}
        <span style={{ color: "var(--accent)" }}>■</span> pushes risk down
      </p>
    </div>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();

  const feedback = useMutation({
    mutationFn: async (status: string) =>
      (await api.post<Alert>(`/api/v1/alerts/${alert.id}/feedback`, {
        feedback_status: status,
        feedback_note: note || null,
      })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const fb = FEEDBACK_LABEL[alert.feedback_status] ?? { label: alert.feedback_status, cls: "" };
  const scorePct = Math.min(100, Math.round(alert.score * 100));

  return (
    <div className="panel" style={{ borderColor: alert.feedback_status === "open" ? "var(--alert)" : "var(--line)" }}>
      <div className="panel-body">
        <div className="row between">
          <div>
            <div className="row" style={{ gap: "0.6rem" }}>
              <strong className="mono">{alert.transaction_id.slice(0, 8)}…</strong>
              <span className="badge">{alert.dataset}</span>
              <span className={`badge ${fb.cls}`}>{fb.label}</span>
            </div>
            <div className="sub">{new Date(alert.created_at).toLocaleString()}</div>
          </div>
          <button className="ghost" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Collapse" : "Investigate"}
          </button>
        </div>

        <div className="scorebar">
          <div className={`fill ${alert.score >= alert.threshold ? "over" : ""}`} style={{ width: `${scorePct}%` }} />
          <div className="thr" style={{ left: `${Math.round(alert.threshold * 100)}%` }} />
        </div>
        <div className="row between sub" style={{ fontSize: "0.72rem" }}>
          <span>score {alert.score.toFixed(4)}</span>
          <span>threshold {alert.threshold.toFixed(4)}</span>
        </div>

        {expanded && (
          <div className="stack" style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--line)" }}>
            <h3 style={{ fontSize: "0.82rem" }}>Why the model flagged it</h3>
            <ShapWaterfall drivers={alert.risk_drivers} />

            {alert.feedback_status === "open" && (
              <div className="stack" style={{ marginTop: "0.5rem" }}>
                <div className="field">
                  <label htmlFor={`note-${alert.id}`}>Reviewer note</label>
                  <textarea id={`note-${alert.id}`} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
                </div>
                <div className="row">
                  <button className="danger" disabled={feedback.isPending} onClick={() => feedback.mutate("confirmed_fraud")}>
                    Confirm fraud
                  </button>
                  <button className="primary" disabled={feedback.isPending} onClick={() => feedback.mutate("false_positive")}>
                    Mark false positive
                  </button>
                  <button disabled={feedback.isPending} onClick={() => feedback.mutate("escalated")}>
                    Escalate
                  </button>
                  {feedback.isPending && <InlineSpinner />}
                </div>
                {feedback.isError && (
                  <div className="field-error" role="alert">{toApiError(feedback.error).message}</div>
                )}
              </div>
            )}
            {alert.feedback_note && (
              <p className="sub"><strong>Note:</strong> {alert.feedback_note}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const DEMO_ALERTS: Alert[] = [
  {
    id: "alt_demo_01",
    transaction_id: "tx_cycle_9921b7a2c3e1",
    payment_id: "pmt_9921",
    score: 0.8420,
    threshold: 0.6500,
    dataset: "BankSim-FedProx",
    created_at: new Date().toISOString(),
    feedback_status: "open",
    feedback_note: null,
    model_artifact: "fedprox_ensemble_v1",
    graph_evidence: { cycle_hops: 3 },
    risk_drivers: [
      { feature: "in_cycle", shap: 0.382, value: 1, family: "graph" },
      { feature: "log_amount", shap: 0.245, value: 7.28, family: "tabular" },
      { feature: "fan_in", shap: 0.174, value: 6, family: "graph" },
      { feature: "cycle_len", shap: 0.081, value: 3, family: "graph" },
      { feature: "step", shap: -0.040, value: 142, family: "tabular" },
    ],
  },
  {
    id: "alt_demo_02",
    transaction_id: "tx_burst_4410a8b9e0f3",
    payment_id: "pmt_4410",
    score: 0.7315,
    threshold: 0.6500,
    dataset: "synth_erp",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    feedback_status: "confirmed_fraud",
    feedback_note: "Cross-bank cycle detected with rapid velocity spike.",
    model_artifact: "fedprox_ensemble_v1",
    graph_evidence: { burst_score: 0.85 },
    risk_drivers: [
      { feature: "vendor_change_7d", shap: 0.310, value: 1, family: "temporal" },
      { feature: "amount", shap: 0.215, value: 4890.0, family: "tabular" },
      { feature: "post_hour", shap: 0.120, value: 23, family: "temporal" },
      { feature: "is_weekend", shap: 0.095, value: 1, family: "temporal" },
    ],
  },
];

function AlertQueue() {
  const { data: rawData, isLoading, isError } = useAlerts();

  if (isLoading) {
    return <div className="panel"><h2>Alert Queue</h2><div className="panel-body"><SkeletonRows rows={4} cols={1} /></div></div>;
  }

  const data = (rawData && rawData.length > 0) ? rawData : (isError ? DEMO_ALERTS : rawData);

  if (!data || data.length === 0) {
    return (
      <div className="panel"><h2>Alert Queue</h2>
        <EmptyState icon="✓" title="No alerts" hint="Nothing has crossed the fraud threshold yet — post a payment to see the live pipeline in action." />
      </div>
    );
  }

  return (
    <div className="stack">
      {isError && (
        <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "6px", padding: "0.6rem 0.9rem", fontSize: "0.8rem", color: "var(--ink)" }}>
          ⚡ <strong>Demo Mode:</strong> Live backend server offline. Displaying benchmark test alerts with SHAP explainability.
        </div>
      )}
      {data.map((a) => <AlertCard key={a.id} alert={a} />)}
    </div>
  );
}

export default function Alerts() {
  return (
    <div className="stack">
      <h1>Alert Queue</h1>
      <p className="sub">Ranked by score. Expand an alert to see its SHAP driver breakdown and record a disposition.</p>
      <ErrorBoundary panelName="Alert queue">
        <AlertQueue />
      </ErrorBoundary>
    </div>
  );
}
