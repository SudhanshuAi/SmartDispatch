import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import { api } from "../../api/client";
import type { DashboardSnapshot, Location } from "../../types";

const statusColor: Record<string, string> = {
  available: "#5ec27a",
  en_route: "#2bb3a3",
  at_pickup: "#e6a23c",
  in_trip: "#5b9fd6",
  on_break: "#8fa3b8",
  offline: "#e85d5d",
};

function markerIcon(status: string) {
  const color = statusColor[status] ?? "#8fa3b8";
  return L.divIcon({
    className: "",
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 0 2px ${color}55"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
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
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, []);

  const center = useMemo<[number, number]>(() => {
    const withPos = data?.drivers.find((d) => d.driver.last_lat != null && d.driver.last_lng != null);
    if (withPos?.driver.last_lat != null && withPos.driver.last_lng != null) {
      return [withPos.driver.last_lat, withPos.driver.last_lng];
    }
    if (locations[0]) return [locations[0].lat, locations[0].lng];
    return [28.6139, 77.209];
  }, [data, locations]);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Fleet map</h1>
          <p>Live driver positions and key event locations. Colors reflect driver status.</p>
        </div>
      </div>
      {error && <div className="flash err">{error}</div>}
      <div className="map-wrap">
        <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
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
          {data?.drivers.map(({ driver, current_trip }) =>
            driver.last_lat != null && driver.last_lng != null ? (
              <Marker
                key={driver.id}
                position={[driver.last_lat, driver.last_lng]}
                icon={markerIcon(driver.status)}
              >
                <Popup>
                  <strong>{driver.full_name}</strong>
                  <br />
                  {driver.status} · {driver.vehicle?.plate_number}
                  <br />
                  {current_trip ? `Trip ${current_trip.status}` : "No active trip"}
                </Popup>
              </Marker>
            ) : null,
          )}
        </MapContainer>
      </div>
      <div className="row-actions muted" style={{ fontSize: "0.85rem" }}>
        {Object.entries(statusColor).map(([k, v]) => (
          <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: v }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
