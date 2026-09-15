import type { ReactNode } from "react";

/** Skeleton rows for a table/list still loading — never a blank flash. */
export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="row skeleton-row" style={{ gap: "1rem" }}>
          {Array.from({ length: cols }).map((__, c) => (
            <div key={c} className="skeleton skeleton-line" style={{ flex: 1 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function InlineSpinner({ label }: { label?: string }) {
  return (
    <span className="row" style={{ gap: "0.5rem" }} role="status">
      <span className="spinner" aria-hidden="true" />
      {label && <span className="sub">{label}</span>}
    </span>
  );
}

export function EmptyState({
  icon = "–",
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-block">
      <div className="state-icon" aria-hidden="true">{icon}</div>
      <div className="state-title">{title}</div>
      {hint && <div className="sub">{hint}</div>}
      {action && <div className="state-action">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  correlationId,
  onRetry,
}: {
  title?: string;
  message: string;
  correlationId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="state-block error">
      <div className="state-icon" aria-hidden="true">!</div>
      <div className="state-title">{title}</div>
      <div className="sub">{message}</div>
      {correlationId && (
        <div className="sub mono" style={{ fontSize: "0.7rem" }}>ref: {correlationId}</div>
      )}
      {onRetry && (
        <div className="state-action">
          <button className="primary" onClick={onRetry}>Retry</button>
        </div>
      )}
    </div>
  );
}
