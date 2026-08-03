import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { DashboardSnapshot } from "../../types";

export function DashboardPage() {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    try {
      setData(await api.dashboard());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  async function runBatch() {
    try {
      const r = (await api.runBatch()) as { trips_created: number; unmatched: unknown[] };
      setMsg(`Batch complete: ${r.trips_created} trips, ${r.unmatched?.length ?? 0} unmatched.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Batch failed");
    }
  }

  const c = data?.counts;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Ops dashboard</h1>
          <p>Live fleet and guest states. Polls every 8s until WebSockets (M6).</p>
        </div>
        <div className="row-actions">
          <button className="btn" onClick={load}>
            Refresh
          </button>
          <button className="btn primary" onClick={runBatch}>
            Run pre-day batch
          </button>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      {msg && <div className="flash ok">{msg}</div>}
      <div className="stats">
        <div className="stat">
          <div className="label">Drivers free</div>
          <div className="value">
            {c?.drivers_available ?? "—"}/{c?.drivers_total ?? "—"}
          </div>
        </div>
        <div className="stat">
          <div className="label">Waiting</div>
          <div className="value">{c?.guests_waiting ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Assigned</div>
          <div className="value">{c?.guests_assigned ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">In transit</div>
          <div className="value">{c?.guests_in_transit ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="label">Pending requests</div>
          <div className="value">{c?.pending_requests ?? "—"}</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Drivers</h2>
            <Link to="/admin/map">Open map</Link>
          </div>
          <div className="scroll-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Vehicle</th>
                  <th>Trip</th>
                </tr>
              </thead>
              <tbody>
                {data?.drivers.map(({ driver, current_trip }) => (
                  <tr key={driver.id}>
                    <td>{driver.full_name}</td>
                    <td>
                      <span className={`badge ${driver.status}`}>{driver.status}</span>
                    </td>
                    <td>
                      {driver.vehicle?.plate_number}
                      <div className="muted" style={{ fontSize: "0.8rem" }}>
                        {driver.vehicle?.seat_capacity}s / {driver.vehicle?.luggage_capacity}l
                      </div>
                    </td>
                    <td>
                      {current_trip ? (
                        <span className={`badge ${current_trip.status}`}>{current_trip.status}</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Guests</h2>
            <Link to="/admin/requests">Review requests</Link>
          </div>
          <div className="scroll-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>State</th>
                  <th>Party</th>
                  <th>ETA</th>
                </tr>
              </thead>
              <tbody>
                {data?.guests.slice(0, 80).map(({ guest, state }) => (
                  <tr key={guest.id}>
                    <td>
                      {guest.full_name}
                      {guest.priority && <span className="badge">VIP</span>}
                    </td>
                    <td>
                      <span className={`badge ${state}`}>{state}</span>
                    </td>
                    <td>
                      {guest.party_size} / {guest.luggage_count} bags
                    </td>
                    <td className="muted">
                      {guest.travel_eta ? new Date(guest.travel_eta).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Pending ride requests</h2>
        </div>
        <div className="scroll-table">
          <table>
            <thead>
              <tr>
                <th>Guest</th>
                <th>Party</th>
                <th>Waiting since</th>
              </tr>
            </thead>
            <tbody>
              {(data?.pending_ride_requests.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={3} className="muted">
                    No pending requests. Seed a few from Ride requests.
                  </td>
                </tr>
              )}
              {data?.pending_ride_requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.guest_name ?? r.guest_id.slice(0, 8)}</td>
                  <td>
                    {r.party_size} / {r.luggage_count}
                  </td>
                  <td>{new Date(r.wait_started_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
