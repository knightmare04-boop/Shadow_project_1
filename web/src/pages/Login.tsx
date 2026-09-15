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

  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={onSubmit} className="panel" style={{ width: 340 }}>
        <h2>Sign in</h2>
        <div className="panel-body stack">
          <h1 style={{ fontSize: "1.3rem" }}>The Self-Auditing Ledger</h1>
          <p className="sub">Procure-to-Pay ERP + forensic audit console</p>

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
