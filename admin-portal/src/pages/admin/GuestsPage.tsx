import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import type { Guest, Location } from "../../types";

export function GuestsPage() {
  const [guests, setGuests] = useState<Guest[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [selected, setSelected] = useState<Guest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [walkIn, setWalkIn] = useState({
    email: "",
    full_name: "",
    phone: "",
    party_size: 1,
    luggage_count: 1,
    travel_mode: "flight",
    travel_ref: "",
    pickup_location_id: "",
    accommodation_id: "",
    priority: false,
  });

  async function load() {
    const [g, locs] = await Promise.all([api.guests(), api.locations()]);
    setGuests(g);
    setLocations(locs);
    if (!walkIn.pickup_location_id && locs[0]) {
      const airport = locs.find((l) => l.type === "airport") ?? locs[0];
      const hotel = locs.find((l) => l.type === "hotel") ?? locs[0];
      setWalkIn((w) => ({
        ...w,
        pickup_location_id: airport.id,
        accommodation_id: hotel.id,
      }));
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function saveCorrection(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    try {
      await api.updateGuest(selected.id, {
        full_name: selected.full_name,
        phone: selected.phone,
        party_size: selected.party_size,
        luggage_count: selected.luggage_count,
        travel_eta: selected.travel_eta,
        travel_mode: selected.travel_mode,
        travel_ref: selected.travel_ref,
        pickup_location_id: selected.pickup_location_id,
        accommodation_id: selected.accommodation_id,
        priority: selected.priority,
        attendance_status: selected.attendance_status,
      });
      setFlash("Guest record updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function createWalkIn(e: FormEvent) {
    e.preventDefault();
    try {
      await api.walkInGuest({
        ...walkIn,
        party_size: Number(walkIn.party_size),
        luggage_count: Number(walkIn.luggage_count),
        travel_eta: new Date().toISOString(),
      });
      setFlash(`Walk-in ${walkIn.full_name} added.`);
      setWalkIn((w) => ({ ...w, email: "", full_name: "", phone: "", travel_ref: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Walk-in failed");
    }
  }

  const locName = (id: string | null) => locations.find((l) => l.id === id)?.name ?? "—";

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Guests</h1>
          <p>Correct flight/train details and walk-ins manually — no auto-import.</p>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      {flash && <div className="flash ok">{flash}</div>}

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Correct guest record</h2>
          </div>
          <div className="form-grid">
            <label>
              Select guest
              <select
                value={selected?.id ?? ""}
                onChange={(e) => setSelected(guests.find((g) => g.id === e.target.value) ?? null)}
              >
                <option value="">Choose…</option>
                {guests.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.full_name} ({g.travel_ref ?? "no ref"})
                  </option>
                ))}
              </select>
            </label>
          </div>
          {selected && (
            <form className="form-grid" onSubmit={saveCorrection}>
              <label>
                Name
                <input
                  value={selected.full_name ?? ""}
                  onChange={(e) => setSelected({ ...selected, full_name: e.target.value })}
                />
              </label>
              <label>
                Phone
                <input
                  value={selected.phone ?? ""}
                  onChange={(e) => setSelected({ ...selected, phone: e.target.value })}
                />
              </label>
              <label>
                Travel mode
                <select
                  value={selected.travel_mode ?? "flight"}
                  onChange={(e) => setSelected({ ...selected, travel_mode: e.target.value })}
                >
                  <option value="flight">flight</option>
                  <option value="train">train</option>
                </select>
              </label>
              <label>
                Flight / train #
                <input
                  value={selected.travel_ref ?? ""}
                  onChange={(e) => setSelected({ ...selected, travel_ref: e.target.value })}
                />
              </label>
              <label>
                Travel ETA
                <input
                  type="datetime-local"
                  value={
                    selected.travel_eta
                      ? new Date(selected.travel_eta).toISOString().slice(0, 16)
                      : ""
                  }
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      travel_eta: e.target.value ? new Date(e.target.value).toISOString() : null,
                    })
                  }
                />
              </label>
              <label>
                Party size
                <input
                  type="number"
                  min={1}
                  value={selected.party_size}
                  onChange={(e) => setSelected({ ...selected, party_size: Number(e.target.value) })}
                />
              </label>
              <label>
                Luggage
                <input
                  type="number"
                  min={0}
                  value={selected.luggage_count}
                  onChange={(e) => setSelected({ ...selected, luggage_count: Number(e.target.value) })}
                />
              </label>
              <label>
                Pickup
                <select
                  value={selected.pickup_location_id ?? ""}
                  onChange={(e) => setSelected({ ...selected, pickup_location_id: e.target.value })}
                >
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Accommodation
                <select
                  value={selected.accommodation_id ?? ""}
                  onChange={(e) => setSelected({ ...selected, accommodation_id: e.target.value })}
                >
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Priority VIP
                <select
                  value={selected.priority ? "yes" : "no"}
                  onChange={(e) => setSelected({ ...selected, priority: e.target.value === "yes" })}
                >
                  <option value="no">no</option>
                  <option value="yes">yes</option>
                </select>
              </label>
              <label>
                Attendance
                <select
                  value={selected.attendance_status ?? "expected"}
                  onChange={(e) =>
                    setSelected({ ...selected, attendance_status: e.target.value })
                  }
                >
                  <option value="expected">expected</option>
                  <option value="checked_in">checked_in</option>
                  <option value="no_show">no_show</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </label>
              <div style={{ display: "flex", alignItems: "end" }}>
                <button className="btn primary" type="submit">
                  Save correction
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Walk-in guest</h2>
          </div>
          <form className="form-grid" onSubmit={createWalkIn}>
            <label>
              Name
              <input
                required
                value={walkIn.full_name}
                onChange={(e) => setWalkIn({ ...walkIn, full_name: e.target.value })}
              />
            </label>
            <label>
              Email
              <input
                required
                type="email"
                value={walkIn.email}
                onChange={(e) => setWalkIn({ ...walkIn, email: e.target.value })}
              />
            </label>
            <label>
              Phone
              <input value={walkIn.phone} onChange={(e) => setWalkIn({ ...walkIn, phone: e.target.value })} />
            </label>
            <label>
              Travel ref
              <input
                value={walkIn.travel_ref}
                onChange={(e) => setWalkIn({ ...walkIn, travel_ref: e.target.value })}
              />
            </label>
            <label>
              Pickup
              <select
                value={walkIn.pickup_location_id}
                onChange={(e) => setWalkIn({ ...walkIn, pickup_location_id: e.target.value })}
              >
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Hotel
              <select
                value={walkIn.accommodation_id}
                onChange={(e) => setWalkIn({ ...walkIn, accommodation_id: e.target.value })}
              >
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ display: "flex", alignItems: "end" }}>
              <button className="btn primary" type="submit">
                Add walk-in
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Guest list ({guests.length})</h2>
        </div>
        <div className="scroll-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Travel</th>
                <th>Pickup → Hotel</th>
                <th>Attendance</th>
                <th>Party</th>
              </tr>
            </thead>
            <tbody>
              {guests.slice(0, 100).map((g) => (
                <tr key={g.id} style={{ cursor: "pointer" }} onClick={() => setSelected(g)}>
                  <td>
                    {g.full_name} {g.priority && <span className="badge">VIP</span>}
                  </td>
                  <td>
                    {g.travel_mode} {g.travel_ref}
                    <div className="muted" style={{ fontSize: "0.8rem" }}>
                      {g.travel_eta ? new Date(g.travel_eta).toLocaleString() : "—"}
                    </div>
                  </td>
                  <td>
                    {locName(g.pickup_location_id)} → {locName(g.accommodation_id)}
                  </td>
                  <td>
                    <span className="badge">{g.attendance_status}</span>
                  </td>
                  <td>
                    {g.party_size} / {g.luggage_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
