import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/admin", end: true, label: "Dashboard" },
  { to: "/admin/map", label: "Fleet map" },
  { to: "/admin/requests", label: "Ride requests" },
  { to: "/admin/drivers", label: "Drivers" },
  { to: "/admin/guests", label: "Guests" },
  { to: "/admin/override", label: "Override" },
];

export function AdminShell() {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          Smart<span>Dispatch</span>
        </div>
        <nav className="nav">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ marginTop: "auto", padding: "0.5rem" }}>
          <div className="muted" style={{ fontSize: "0.85rem" }}>
            {user?.full_name}
            <br />
            <span className="badge">admin</span>
          </div>
          <button className="btn ghost" style={{ marginTop: "0.6rem" }} onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
