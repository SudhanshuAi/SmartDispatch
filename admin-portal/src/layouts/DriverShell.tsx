import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/** Driver role — single-trip UI only; no ops/fleet navigation. */
export function DriverShell() {
  const { user, logout } = useAuth();
  return (
    <div className="login-wrap">
      <div className="login-card stack driver-shell">
        <div className="row-actions" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1>
              Smart<span style={{ color: "var(--accent)" }}>Dispatch</span>
            </h1>
            <p className="muted" style={{ margin: "0.25rem 0 0" }}>
              Driver · {user?.full_name}
            </p>
          </div>
          <button className="btn" onClick={logout}>
            Sign out
          </button>
        </div>
        <Outlet />
      </div>
    </div>
  );
}
