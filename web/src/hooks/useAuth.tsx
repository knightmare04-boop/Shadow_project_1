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
    api.get<CurrentUser>("/api/v1/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => setToken(null)) // stale/expired token — silently log out
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
      setError(apiErr.message);
      throw apiErr;
    }
  }

  function logout() {
    setToken(null);
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
