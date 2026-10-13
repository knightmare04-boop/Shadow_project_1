import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function quickLogin(userEmail: string) {
    setEmail(userEmail);
    setPassword("devpassword123");
    setSubmitting(true);
    setError(null);
    try {
      await login(userEmail, "devpassword123");
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
      <form onSubmit={onSubmit} className="panel" style={{ width: 380, maxWidth: "100%" }}>
        <h2>Sign in</h2>
        <div className="panel-body stack">
          <h1 style={{ fontSize: "1.25rem", margin: 0 }}>The Self-Auditing Ledger</h1>
          <p className="sub" style={{ margin: 0 }}>Procure-to-Pay ERP + forensic audit & federated network console</p>

          <div style={{ background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.25)", borderRadius: "6px", padding: "0.75rem", fontSize: "0.8rem" }}>
            <div style={{ fontWeight: 600, marginBottom: "0.4rem", color: "var(--accent)" }}>Quick Dev / Demo Sign-in:</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <button
                type="button"
                className="ghost"
                style={{ textAlign: "left", padding: "0.3rem 0.5rem", fontSize: "0.75rem", border: "1px solid var(--line)" }}
                onClick={() => quickLogin("auditor@shadow-ledger.app")}
              >
                🛡️ <strong>Auditor:</strong> auditor@shadow-ledger.app
              </button>
              <button
                type="button"
                className="ghost"
                style={{ textAlign: "left", padding: "0.3rem 0.5rem", fontSize: "0.75rem", border: "1px solid var(--line)" }}
                onClick={() => quickLogin("admin@shadow-ledger.app")}
              >
                ⚡ <strong>Admin:</strong> admin@shadow-ledger.app
              </button>
              <button
                type="button"
                className="ghost"
                style={{ textAlign: "left", padding: "0.3rem 0.5rem", fontSize: "0.75rem", border: "1px solid var(--line)" }}
                onClick={() => quickLogin("clerk@shadow-ledger.app")}
              >
                📝 <strong>Clerk:</strong> clerk@shadow-ledger.app
              </button>
            </div>
            <div style={{ marginTop: "0.4rem", fontSize: "0.72rem", color: "var(--sub)" }}>
              Default password: <code className="mono">devpassword123</code>
            </div>
          </div>

          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required autoComplete="username"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" required autoComplete="current-password"
                   value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>

          {error && <div className="field-error" role="alert">{error}</div>}

          <button type="submit" className="primary" disabled={submitting} style={{ width: "100%" }}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </div>
  );
}
