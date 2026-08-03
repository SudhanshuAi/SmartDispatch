import { useEffect, useState, type FormEvent } from "react";
import { api } from "../../api/client";
import type { Driver } from "../../types";

const emptyForm = {
  email: "",
  full_name: "",
  phone: "",
  plate_number: "",
  seat_capacity: 4,
  luggage_capacity: 2,
  make_model: "Sedan",
};

export function DriversPage() {
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  async function load() {
    setDrivers(await api.drivers());
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.onboardDriver({
        ...form,
        seat_capacity: Number(form.seat_capacity),
        luggage_capacity: Number(form.luggage_capacity),
        last_lat: 28.6139 + Math.random() * 0.02,
        last_lng: 77.209 + Math.random() * 0.02,
      });
      setFlash(`Onboarded ${form.full_name}`);
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Onboard failed");
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Drivers</h1>
          <p>Manual onboarding only — no self-signup. Enter name, contact, plate, and capacity.</p>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      {flash && <div className="flash ok">{flash}</div>}

      <div className="panel">
        <div className="panel-head">
          <h2>Onboard driver</h2>
        </div>
        <form className="form-grid" onSubmit={onSubmit}>
          <label>
            Full name
            <input
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </label>
          <label>
            Email
            <input
              required
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label>
            Phone
            <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </label>
          <label>
            Vehicle number
            <input
              required
              value={form.plate_number}
              onChange={(e) => setForm({ ...form, plate_number: e.target.value })}
            />
          </label>
          <label>
            Seat capacity
            <input
              type="number"
              min={1}
              value={form.seat_capacity}
              onChange={(e) => setForm({ ...form, seat_capacity: Number(e.target.value) })}
            />
          </label>
          <label>
            Luggage capacity
            <input
              type="number"
              min={0}
              value={form.luggage_capacity}
              onChange={(e) => setForm({ ...form, luggage_capacity: Number(e.target.value) })}
            />
          </label>
          <label>
            Make / model
            <input value={form.make_model} onChange={(e) => setForm({ ...form, make_model: e.target.value })} />
          </label>
          <div style={{ display: "flex", alignItems: "end" }}>
            <button className="btn primary" type="submit">
              Add driver
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Fleet roster ({drivers.length})</h2>
        </div>
        <div className="scroll-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Contact</th>
                <th>Vehicle</th>
                <th>Capacity</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d) => (
                <tr key={d.id}>
                  <td>{d.full_name}</td>
                  <td>
                    {d.phone}
                    <div className="muted" style={{ fontSize: "0.8rem" }}>
                      {d.email}
                    </div>
                  </td>
                  <td>{d.vehicle?.plate_number}</td>
                  <td>
                    {d.vehicle?.seat_capacity} seats / {d.vehicle?.luggage_capacity} luggage
                  </td>
                  <td>
                    <span className={`badge ${d.status}`}>{d.status}</span>
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
