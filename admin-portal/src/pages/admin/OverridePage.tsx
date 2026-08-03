import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import type { Driver, Guest, Trip } from "../../types";

export function OverridePage() {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [guests, setGuests] = useState<Guest[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const [reassign, setReassign] = useState({ trip_id: "", new_driver_id: "", reason: "" });
  const [down, setDown] = useState({ driver_id: "", reason: "breakdown" });
  const [force, setForce] = useState({ guest_id: "", driver_id: "", reason: "priority guest" });

  async function load() {
    const [d, g, t] = await Promise.all([api.drivers(), api.guests(), api.trips()]);
    setDrivers(d);
    setGuests(g);
    setTrips(t.filter((x) => !["completed", "cancelled"].includes(x.status)));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function onReassign(e: FormEvent) {
    e.preventDefault();
    try {
      const trip = trips.find((t) => t.id === reassign.trip_id);
      await api.reassign({
        trip_id: reassign.trip_id,
        new_driver_id: reassign.new_driver_id,
        expected_route_version: trip?.route_version,
        reason: reassign.reason,
      });
      setFlash("Trip reassigned.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reassign failed");
    }
  }

  async function onDown(e: FormEvent) {
    e.preventDefault();
    try {
      await api.vehicleDown(down);
      setFlash("Vehicle marked down; open trips cancelled and guests requeued.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function onForce(e: FormEvent) {
    e.preventDefault();
    try {
      await api.forceMatch(force);
      setFlash("Force-match created (manual override — bypasses auto matcher).");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Force-match failed");
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Manual override</h1>
          <p>Edge cases only: reassign, vehicle down, or force-match when auto-match cannot.</p>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      {flash && <div className="flash ok">{flash}</div>}

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Reassign trip</h2>
          </div>
          <form className="form-grid" onSubmit={onReassign}>
            <label>
              Trip
              <select
                required
                value={reassign.trip_id}
                onChange={(e) => setReassign({ ...reassign, trip_id: e.target.value })}
              >
                <option value="">Choose…</option>
                {trips.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.status} · {t.id.slice(0, 8)} · v{t.route_version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              New driver
              <select
                required
                value={reassign.new_driver_id}
                onChange={(e) => setReassign({ ...reassign, new_driver_id: e.target.value })}
              >
                <option value="">Choose…</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name} ({d.status})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Reason
              <input
                value={reassign.reason}
                onChange={(e) => setReassign({ ...reassign, reason: e.target.value })}
              />
            </label>
            <div style={{ display: "flex", alignItems: "end" }}>
              <button className="btn primary" type="submit">
                Reassign
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Mark vehicle down</h2>
          </div>
          <form className="form-grid" onSubmit={onDown}>
            <label>
              Driver / vehicle
              <select
                required
                value={down.driver_id}
                onChange={(e) => setDown({ ...down, driver_id: e.target.value })}
              >
                <option value="">Choose…</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name} · {d.vehicle?.plate_number}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Reason
              <input value={down.reason} onChange={(e) => setDown({ ...down, reason: e.target.value })} />
            </label>
            <div style={{ display: "flex", alignItems: "end" }}>
              <button className="btn danger" type="submit">
                Mark down
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Force-match guest → driver</h2>
        </div>
        <form className="form-grid" onSubmit={onForce}>
          <label>
            Guest
            <select
              required
              value={force.guest_id}
              onChange={(e) => setForce({ ...force, guest_id: e.target.value })}
            >
              <option value="">Choose…</option>
              {guests.slice(0, 80).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Driver
            <select
              required
              value={force.driver_id}
              onChange={(e) => setForce({ ...force, driver_id: e.target.value })}
            >
              <option value="">Choose…</option>
              {drivers
                .filter((d) => d.status === "available")
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name} · {d.vehicle?.plate_number}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Reason
            <input value={force.reason} onChange={(e) => setForce({ ...force, reason: e.target.value })} />
          </label>
          <div style={{ display: "flex", alignItems: "end" }}>
            <button className="btn primary" type="submit">
              Force match
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
