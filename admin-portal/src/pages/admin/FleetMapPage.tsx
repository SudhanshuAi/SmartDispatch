import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import { api } from "../../api/client";
import type { DashboardSnapshot, Location, Trip } from "../../types";

/** Distinct colors — at_pickup / in_trip must stand out from available / on_break */
const statusColor: Record<string, string> = {
  available: "#5ec27a",
  en_route: "#2bb3a3",
  at_pickup: "#f0a020",
  in_trip: "#3b82f6",
  on_break: "#8fa3b8",
  offline: "#e85d5d",
};

const ACTIVE_TRIP_STATUSES = new Set([
  "offered",
  "accepted",
  "en_route",
  "at_pickup",
  "in_progress",
]);

/** Prefer trip phase for map color when driver is on an active trip */
function mapDisplayStatus(driverStatus: string, trip: Trip | null): string {
  if (trip && ACTIVE_TRIP_STATUSES.has(trip.status)) {
    if (trip.status === "at_pickup") return "at_pickup";
    if (trip.status === "in_progress") return "in_trip";
    if (trip.status === "en_route" || trip.status === "accepted" || trip.status === "offered") {
      return "en_route";
    }
  }
  return driverStatus;
}

function markerIcon(status: string, *, active: boolean) {
  const color = statusColor[status] ?? "#8fa3b8";
  const size = active ? 18 : 14;
  const ring = active ? 3 : 2;
  return L.divIcon({
    className: "fleet-marker",
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:${ring}px solid #fff;box-shadow:0 0 0 2px ${color}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function FitActiveDrivers({
  points,
}: {
  points: [number, number][];
}) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 12));
      return;
    }
    const bounds = L.latLngBounds(points.map((p) => L.latLng(p[0], p[1])));
    map.fitBounds(bounds.pad(0.25));
  }, [map, points]);
  return null;
}

export function FleetMapPage() {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [d, locs] = await Promise.all([api.dashboard(), api.locations()]);
        setData(d);
        setLocations(locs);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load map");
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const driverMarkers = useMemo(() => {
    if (!data) return [];
    return data.drivers
      .map(({ driver, current_trip }) => {
        const status = mapDisplayStatus(driver.status, current_trip);
        const active = ["en_route", "at_pickup", "in_trip"].includes(status);
        let lat = driver.last_lat;
        let lng = driver.last_lng;
        // If GPS missing but on trip, fall back to trip origin so marker still shows
        if ((lat == null || lng == null) && current_trip) {
          const origin = locations.find((l) => l.id === current_trip.origin_location_id);
          if (origin) {
            lat = origin.lat;
            lng = origin.lng;
          }
        }
        if (lat == null || lng == null) return null;
        return {
          id: driver.id,
          name: driver.full_name,
          plate: driver.vehicle?.plate_number,
          status,
          active,
          lat,
          lng,
          tripStatus: current_trip?.status ?? null,
        };
      })
      .filter((m): m is NonNullable<typeof m> => m != null);
  }, [data, locations]);

  const activePoints = useMemo(
    () => driverMarkers.filter((m) => m.active).map((m) => [m.lat, m.lng] as [number, number]),
    [driverMarkers],
  );

  const center = useMemo<[number, number]>(() => {
    if (activePoints[0]) return activePoints[0];
    if (driverMarkers[0]) return [driverMarkers[0].lat, driverMarkers[0].lng];
    if (locations[0]) return [locations[0].lat, locations[0].lng];
    return [28.6139, 77.209];
  }, [activePoints, driverMarkers, locations]);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Fleet map</h1>
          <p>
            Live driver positions. Active trips use larger markers — orange = at pickup, blue =
            in trip, teal = en route.
          </p>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      <div className="map-wrap">
        <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitActiveDrivers points={activePoints} />
          {locations.map((loc) => (
            <Marker
              key={loc.id}
              position={[loc.lat, loc.lng]}
              icon={L.divIcon({
                className: "",
                html: `<div style="padding:2px 6px;background:#222c38;color:#e8eef4;border:1px solid #2bb3a3;border-radius:4px;font:11px IBM Plex Sans,sans-serif">${loc.type}</div>`,
                iconSize: [60, 20],
                iconAnchor: [30, 10],
              })}
            >
              <Popup>
                <strong>{loc.name}</strong>
                <br />
                {loc.address}
              </Popup>
            </Marker>
          ))}
          {driverMarkers.map((m) => (
            <Marker
              key={`${m.id}-${m.status}-${m.lat.toFixed(4)}-${m.lng.toFixed(4)}`}
              position={[m.lat, m.lng]}
              icon={markerIcon(m.status, { active: m.active })}
              zIndexOffset={m.active ? 1000 : 0}
            >
              <Popup>
                <strong>{m.name}</strong>
                <br />
                Driver: {m.status} · {m.plate}
                <br />
                {m.tripStatus ? `Trip: ${m.tripStatus}` : "No active trip"}
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <div className="row-actions muted" style={{ fontSize: "0.85rem", flexWrap: "wrap", gap: 12 }}>
        {Object.entries(statusColor).map(([k, v]) => (
          <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: ["at_pickup", "in_trip", "en_route"].includes(k) ? 12 : 10,
                height: ["at_pickup", "in_trip", "en_route"].includes(k) ? 12 : 10,
                borderRadius: "50%",
                background: v,
                border: "1px solid #fff",
              }}
            />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
