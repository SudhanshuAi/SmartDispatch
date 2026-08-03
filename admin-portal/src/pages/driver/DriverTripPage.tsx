import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import type { DriverMe, DriverTrip } from "../../types";

function fmtEta(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function fmtCountdown(secs: number | null | undefined): string {
  if (secs == null || secs <= 0) return "0:00";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function DriverTripPage() {
  const { user } = useAuth();
  const [me, setMe] = useState<DriverMe | null>(null);
  const [trip, setTrip] = useState<DriverTrip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [locStatus, setLocStatus] = useState<"off" | "sharing" | "error">("off");
  const watchRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [m, t] = await Promise.all([api.driverMe(), api.driverTrip()]);
      setMe(m);
      setTrip(t);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  // Live countdown for break remaining
  useEffect(() => {
    if (!me?.on_break || !me.break_remaining_seconds) return;
    const id = window.setInterval(() => {
      setMe((prev) => {
        if (!prev?.break_remaining_seconds) return prev;
        const next = Math.max(0, prev.break_remaining_seconds - 1);
        return { ...prev, break_remaining_seconds: next, on_break: next > 0 || prev.status === "on_break" };
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [me?.on_break, me?.break_until]);

  const onTrip = Boolean(
    trip && ["offered", "accepted", "en_route", "at_pickup", "in_progress"].includes(trip.status),
  );

  // Continuous location while on an active trip
  useEffect(() => {
    if (!onTrip || !navigator.geolocation) {
      if (watchRef.current != null) {
        navigator.geolocation.clearWatch(watchRef.current);
        watchRef.current = null;
      }
      setLocStatus("off");
      return;
    }

    setLocStatus("sharing");
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        void api
          .driverLocation({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            heading: pos.coords.heading ?? undefined,
            speed: pos.coords.speed ?? undefined,
          })
          .catch(() => setLocStatus("error"));
      },
      () => setLocStatus("error"),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );

    return () => {
      if (watchRef.current != null) {
        navigator.geolocation.clearWatch(watchRef.current);
        watchRef.current = null;
      }
    };
  }, [onTrip, trip?.trip_id]);

  async function run(action: () => Promise<unknown>, okMsg: string) {
    setBusy(true);
    setError(null);
    setFlash(null);
    try {
      await action();
      setFlash(okMsg);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  const partyTotal = trip?.guests.reduce((n, g) => n + g.party_size, 0) ?? 0;

  return (
    <div className="stack driver-trip">
      <div className="row-actions" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="muted" style={{ fontSize: "0.85rem" }}>
            {user?.full_name}
            {me?.plate_number ? ` · ${me.plate_number}` : ""}
          </div>
          <div className="row-actions" style={{ marginTop: "0.35rem" }}>
            <span className={`badge ${me?.status ?? ""}`}>{me?.status ?? "…"}</span>
            {locStatus === "sharing" && <span className="badge in_trip">live location</span>}
            {locStatus === "error" && <span className="badge offline">location error</span>}
          </div>
        </div>
        <button className="btn ghost" type="button" onClick={() => void refresh()} disabled={busy}>
          Refresh
        </button>
      </div>

      {error && <div className="flash err">{error}</div>}
      {flash && <div className="flash ok">{flash}</div>}

      {me?.on_break && (
        <div className="flash ok stack" style={{ gap: "0.5rem" }}>
          <strong>Mandatory break / cooldown</strong>
          <p className="muted" style={{ margin: 0 }}>
            Matching will skip you until the break ends ({me.mandatory_break_minutes} min after drop-off).
          </p>
          <div style={{ fontFamily: "var(--display)", fontSize: "2rem" }}>
            {fmtCountdown(me.break_remaining_seconds)}
          </div>
          <button
            className="btn primary"
            disabled={busy || (me.break_remaining_seconds != null && me.break_remaining_seconds > 0)}
            onClick={() => run(() => api.driverEndBreak(), "Back on duty")}
          >
            End break
          </button>
        </div>
      )}

      {!trip && !me?.on_break && (
        <div className="stack" style={{ textAlign: "center", padding: "1.5rem 0" }}>
          <h2 style={{ fontSize: "1.8rem" }}>No active trip</h2>
          <p className="muted">When dispatch assigns you a ride, it will appear here.</p>
        </div>
      )}

      {trip && (
        <>
          <div>
            <div className="row-actions" style={{ marginBottom: "0.5rem" }}>
              <span className={`badge ${trip.status}`}>{trip.status}</span>
              <span className="badge">{trip.trip_type}</span>
            </div>
            <h2 style={{ fontSize: "1.9rem", marginBottom: "0.25rem" }}>Current trip</h2>
          </div>

          <div className="driver-trip-grid">
            <div>
              <div className="muted">Pickup</div>
              <strong>{trip.pickup_name ?? "—"}</strong>
              <div className="muted" style={{ fontSize: "0.85rem" }}>
                {trip.pickup_address}
              </div>
            </div>
            <div>
              <div className="muted">Destination</div>
              <strong>{trip.dest_name ?? "—"}</strong>
              <div className="muted" style={{ fontSize: "0.85rem" }}>
                {trip.dest_address}
              </div>
            </div>
            <div>
              <div className="muted">Target ETA (pickup)</div>
              <strong style={{ fontFamily: "var(--display)", fontSize: "1.6rem" }}>
                {fmtEta(trip.eta_pickup)}
              </strong>
            </div>
            <div>
              <div className="muted">Target ETA (drop)</div>
              <strong style={{ fontFamily: "var(--display)", fontSize: "1.6rem" }}>
                {fmtEta(trip.eta_drop)}
              </strong>
            </div>
          </div>

          <div>
            <div className="muted" style={{ marginBottom: "0.35rem" }}>
              Guests · {partyTotal} pax · {trip.luggage_used} bags
            </div>
            <ul className="guest-list">
              {trip.guests.map((g) => (
                <li key={g.guest_id}>
                  <strong>{g.name}</strong>
                  <span className="muted">
                    {" "}
                    · {g.party_size} pax
                    {g.boarded_at ? " · boarded" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="row-actions">
            {trip.status === "offered" && (
              <>
                <button
                  className="btn primary"
                  disabled={busy}
                  onClick={() => run(() => api.driverAccept(), "Trip accepted — head to pickup")}
                >
                  Accept
                </button>
                <button
                  className="btn danger"
                  disabled={busy}
                  onClick={() =>
                    run(() => api.driverReject("driver declined"), "Rejected — guest re-queued")
                  }
                >
                  Reject
                </button>
              </>
            )}
            {(trip.status === "accepted" || trip.status === "en_route") && (
              <button
                className="btn primary"
                disabled={busy}
                onClick={() => run(() => api.driverStatus("arrived_pickup"), "Arrived at pickup")}
              >
                Arrived at pickup
              </button>
            )}
            {trip.status === "at_pickup" && (
              <button
                className="btn primary"
                disabled={busy}
                onClick={() => run(() => api.driverStatus("boarded"), "Guest boarded")}
              >
                Guest boarded
              </button>
            )}
            {trip.status === "in_progress" && (
              <button
                className="btn primary"
                disabled={busy}
                onClick={() => run(() => api.driverStatus("arrived_drop"), "Drop complete — break started")}
              >
                Arrived at drop
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
