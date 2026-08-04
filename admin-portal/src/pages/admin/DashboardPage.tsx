import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { DashboardSnapshot } from "../../types";

export function DashboardPage() {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [queueDepth, setQueueDepth] = useState<number | null>(null);

  async function load() {
    try {
      const [dash, status] = await Promise.all([api.dashboard(), api.matchingStatus().catch(() => null)]);
      setData(dash);
      if (status) setQueueDepth(status.queue_depth);
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

  async function drainQueue() {
    try {
      const r = await api.processQueue();
      setMsg(
        r.processed
          ? `Queue processed one guest (${r.reason ?? "ok"}).`
          : `Queue idle: ${r.reason ?? "empty"}.`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Queue process failed");
    }
  }

  const c = data?.counts;
  const waiting = data?.guests.filter((g) => g.state === "waiting") ?? [];
  const activeTrips = data?.active_trips ?? [];

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Ops dashboard</h1>
          <p>Fleet, unmatched guests, and upcoming trips. Refreshes every 8s.</p>
        </div>
        <div className="row-actions">
          <button className="btn" onClick={load}>
            Refresh
          </button>
          <button className="btn" onClick={drainQueue}>
            Process queue {queueDepth != null ? `(${queueDepth})` : ""}
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
          <div className="label">Waiting / unmatched</div>
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
        <div className="stat">
          <div className="label">Active trips</div>
          <div className="value">{activeTrips.length}</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Upcoming / active trips</h2>
          </div>
          <div className="scroll-table">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>ETA pickup</th>
                  <th>Seats</th>
                  <th>Guests</th>
                </tr>
              </thead>
              <tbody>
                {activeTrips.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      No active trips. Approve a request or run batch.
                    </td>
                  </tr>
                )}
                {activeTrips.slice(0, 40).map((t) => (
                  <tr key={t.id}>
                    <td>{t.trip_type}</td>
                    <td>
                      <span className={`badge ${t.status}`}>{t.status}</span>
                    </td>
                    <td className="muted">
                      {t.eta_pickup ? new Date(t.eta_pickup).toLocaleString() : "—"}
                    </td>
                    <td>
                      {t.seats_used}s / {t.luggage_used}l
                    </td>
                    <td className="muted">{t.guest_ids?.length ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Unmatched / waiting guests</h2>
            <Link to="/admin/guests">Edit guests</Link>
          </div>
          <div className="scroll-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Party</th>
                  <th>Travel ETA</th>
                </tr>
              </thead>
              <tbody>
                {waiting.length === 0 && (
                  <tr>
                    <td colSpan={3} className="muted">
                      No waiting guests.
                    </td>
                  </tr>
                )}
                {waiting.slice(0, 40).map(({ guest }) => (
                  <tr key={guest.id}>
                    <td>
                      {guest.full_name}
                      {guest.priority && <span className="badge">VIP</span>}
                    </td>
                    <td>
                      {guest.party_size} / {guest.luggage_count}
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
                    No pending requests.
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
