import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, toApiError } from "../lib/api";
import type { CurrentUser, LoginResponse } from "../types/api";

interface AuthState {
  user: CurrentUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export const DEMO_USERS: Record<string, CurrentUser> = {
  "auditor@shadow-ledger.app": {
    id: "usr_demo_auditor",
    email: "auditor@shadow-ledger.app",
    full_name: "Lead Forensic Auditor",
    role: "forensic_auditor",
  },
  "admin@shadow-ledger.app": {
    id: "usr_demo_admin",
    email: "admin@shadow-ledger.app",
    full_name: "System Administrator",
    role: "system_administrator",
  },
  "clerk@shadow-ledger.app": {
    id: "usr_demo_clerk",
    email: "clerk@shadow-ledger.app",
    full_name: "AP Clerk",
    role: "erp_clerk",
  },
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    if (token.startsWith("demo_")) {
      const demoEmail = localStorage.getItem("shadow_ledger_demo_email") || "auditor@shadow-ledger.app";
      setUser(DEMO_USERS[demoEmail] || DEMO_USERS["auditor@shadow-ledger.app"]);
      setLoading(false);
      return;
    }
    api.get<CurrentUser>("/api/v1/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => {
        const demoEmail = localStorage.getItem("shadow_ledger_demo_email");
        if (demoEmail && DEMO_USERS[demoEmail]) {
          setUser(DEMO_USERS[demoEmail]);
        } else {
          setToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    setError(null);
    try {
      const res = await api.post<LoginResponse>("/api/v1/auth/login", { email, password });
      setToken(res.data.access_token);
      const me = await api.get<CurrentUser>("/api/v1/auth/me");
      setUser(me.data);
    } catch (err) {
      const apiErr = toApiError(err);
      const normalizedEmail = email.toLowerCase().trim();
      const demoUser = DEMO_USERS[normalizedEmail];
      // Graceful offline fallback: if backend is down or dev password matches
      if (demoUser && (password === "devpassword123" || apiErr.isNetworkError)) {
        setToken(`demo_${demoUser.role}`);
        localStorage.setItem("shadow_ledger_demo_email", demoUser.email);
        setUser(demoUser);
        return;
      }
      setError(apiErr.message);
      throw apiErr;
    }
  }

  function logout() {
    setToken(null);
    localStorage.removeItem("shadow_ledger_demo_email");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
