import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { InlineSpinner } from "./States";

const NAV = [
  {
    section: "Procure-to-Pay",
    roles: ["erp_clerk", "system_administrator"],
    links: [
      { to: "/vendors", label: "Vendors" },
      { to: "/invoices", label: "Invoices" },
      { to: "/payments", label: "Payments" },
    ],
  },
  {
    section: "Forensic Console",
    roles: ["forensic_auditor", "system_administrator"],
    links: [{ to: "/alerts", label: "Alert Queue" }],
  },
];

export default function Layout() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
        <InlineSpinner label="Loading session…" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <nav className="app-sidebar" aria-label="Primary">
        <div className="app-brand">Self-Auditing Ledger</div>
        {NAV.filter((s) => s.roles.includes(user.role)).map((section) => (
          <div key={section.section}>
            <div className="nav-section-label">{section.section}</div>
            {section.links.map((link) => (
              <NavLink key={link.to} to={link.to}
                       className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                {link.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div style={{ marginTop: "auto", paddingTop: "1rem", borderTop: "1px solid var(--line)" }}>
          <div className="sub" style={{ marginBottom: "0.4rem" }}>{user.full_name}</div>
          <div className="badge" style={{ marginBottom: "0.6rem" }}>{user.role.replace("_", " ")}</div>
          <button className="ghost" onClick={logout} style={{ width: "100%" }}>Sign out</button>
        </div>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
