import { createElement, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import type { GuestLocation, GuestMatch } from "../types";

/**
 * Web map via OpenStreetMap embed (no react-native-maps on web).
 * Native builds use LiveTripMap.native.tsx.
 */
export function LiveTripMap({ match }: { match: GuestMatch }) {
  const lat = match.driver_lat ?? match.pickup?.lat ?? match.destination?.lat ?? 28.6139;
  const lng = match.driver_lng ?? match.pickup?.lng ?? match.destination?.lng ?? 77.209;
  const delta = 0.05;
  const src = useMemo(() => {
    const bbox = `${lng - delta}%2C${lat - delta}%2C${lng + delta}%2C${lat + delta}`;
    return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`;
  }, [lat, lng]);

  return (
    <View style={styles.wrap}>
      {createElement("iframe", {
        title: "Live trip map",
        src,
        style: {
          width: "100%",
          height: 240,
          border: 0,
          borderRadius: 12,
        },
      })}
      <View style={styles.meta}>
        <Text style={styles.title}>Live tracking</Text>
        <Text style={styles.muted}>
          ETA pickup {fmtEta(match.eta_pickup)} · drop {fmtEta(match.eta_drop)}
        </Text>
        {match.driver_name ? (
          <Text style={styles.driver}>
            {match.driver_name}
            {match.vehicle_number ? ` · ${match.vehicle_number}` : ""}
          </Text>
        ) : null}
        {match.pickup && <LocLine label="Pickup" loc={match.pickup} />}
        {match.destination && <LocLine label="Drop" loc={match.destination} />}
      </View>
    </View>
  );
}

function fmtEta(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function LocLine({ label, loc }: { label: string; loc: GuestLocation }) {
  return (
    <Text style={styles.locLine}>
      <Text style={styles.locLabel}>{label}: </Text>
      {loc.name}
    </Text>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: 16,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#d5e0dc",
    backgroundColor: "#eef6f4",
  },
  meta: { padding: 12, gap: 4 },
  title: { fontSize: 16, fontWeight: "700", color: "#0f3d38" },
  muted: { color: "#5a736e" },
  driver: { color: "#0f3d38", fontWeight: "600" },
  locLine: { color: "#0f3d38" },
  locLabel: { fontWeight: "600" },
});
