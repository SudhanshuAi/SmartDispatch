import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@smartdispatch.local");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user?.role === "admin") return <Navigate to="/admin" replace />;
  if (user?.role === "driver") return <Navigate to="/driver" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email.trim());
      if (u.role === "guest") {
        throw new Error("Guests use the Guest app, not this portal.");
      }
      nav(u.role === "admin" ? "/admin" : "/driver");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card stack" onSubmit={onSubmit}>
        <div>
          <h1>
            Smart<span style={{ color: "var(--accent)" }}>Dispatch</span>
          </h1>
          <p className="muted">Operations & driver portal — one app, role-gated views.</p>
        </div>
        {error && <div className="flash err">{error}</div>}
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@smartdispatch.local" />
        </label>
        <button className="btn primary" disabled={busy}>
          {busy ? "Signing in…" : "Continue"}
        </button>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Try <code>admin@smartdispatch.local</code> or <code>driver01@smartdispatch.local</code> from the seed data.
        </p>
      </form>
    </div>
  );
}
