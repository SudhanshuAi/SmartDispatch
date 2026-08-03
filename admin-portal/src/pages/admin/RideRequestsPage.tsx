import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { RideRequest } from "../../types";

export function RideRequestsPage() {
  const [rows, setRows] = useState<RideRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      setRows(await api.rideRequests());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 7000);
    return () => clearInterval(id);
  }, []);

  async function seed() {
    try {
      await api.seedRideRequests();
      setFlash("Seeded demo pending requests.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    }
  }

  async function approve(id: string) {
    setBusyId(id);
    setFlash(null);
    try {
      const r = await api.approveRequest(id);
      setFlash(r.message);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusyId(null);
    }
  }

  async function decline(id: string) {
    setBusyId(id);
    try {
      await api.declineRequest(id);
      setFlash("Request declined.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decline failed");
    } finally {
      setBusyId(null);
    }
  }

  const pending = rows.filter((r) => r.status === "pending_admin");

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Ride requests</h1>
          <p>
            Manual approve/decline only. On approve, the matching engine assigns a driver — you never
            pick one here.
          </p>
        </div>
        <button className="btn" onClick={seed}>
          Seed demo requests
        </button>
      </div>
      {error && <div className="flash err">{error}</div>}
      {flash && <div className="flash ok">{flash}</div>}

      <div className="panel">
        <div className="panel-head">
          <h2>Pending admin review ({pending.length})</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Guest</th>
              <th>Party / luggage</th>
              <th>Waiting since</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {pending.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  Queue empty.
                </td>
              </tr>
            )}
            {pending.map((r) => (
              <tr key={r.id}>
                <td>{r.guest_name ?? r.guest_id.slice(0, 8)}</td>
                <td>
                  {r.party_size} / {r.luggage_count}
                </td>
                <td>{new Date(r.wait_started_at).toLocaleString()}</td>
                <td className="row-actions">
                  <button
                    className="btn primary"
                    disabled={busyId === r.id}
                    onClick={() => approve(r.id)}
                  >
                    Approve
                  </button>
                  <button className="btn danger" disabled={busyId === r.id} onClick={() => decline(r.id)}>
                    Decline
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>All requests</h2>
        </div>
        <div className="scroll-table">
          <table>
            <thead>
              <tr>
                <th>Guest</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.guest_name ?? r.guest_id.slice(0, 8)}</td>
                  <td>
                    <span className={`badge ${r.status}`}>{r.status}</span>
                  </td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
