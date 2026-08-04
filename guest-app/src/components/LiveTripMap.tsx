import { createElement, useMemo, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import type { GuestLocation, GuestMatch } from "../types";

/**
 * Web / default live map. Native builds use LiveTripMap.native.tsx.
 * Renders an OSM embed iframe (RN-web) so the map is visible in the browser.
 */
export function LiveTripMap({ match }: { match: GuestMatch }) {
  const lat = match.driver_lat ?? match.pickup?.lat ?? match.destination?.lat ?? 28.6139;
  const lng = match.driver_lng ?? match.pickup?.lng ?? match.destination?.lng ?? 77.209;
  const [iframeFailed, setIframeFailed] = useState(false);

  const { embedUrl, openUrl, staticUrl } = useMemo(() => {
    const delta = 0.06;
    const bbox = `${lng - delta}%2C${lat - delta}%2C${lng + delta}%2C${lat + delta}`;
    const embedUrl =
      `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`;
    const openUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=13/${lat}/${lng}`;
    const markers: string[] = [];
    if (match.driver_lat != null && match.driver_lng != null) {
      markers.push(`${match.driver_lat},${match.driver_lng},red-pushpin`);
    }
    if (match.pickup) markers.push(`${match.pickup.lat},${match.pickup.lng},orange-pushpin`);
    if (match.destination) {
      markers.push(`${match.destination.lat},${match.destination.lng},green-pushpin`);
    }
    if (!markers.length) markers.push(`${lat},${lng},lightblue1`);
    const staticUrl =
      `https://staticmap.openstreetmap.de/staticmap.php?center=${lat},${lng}` +
      `&zoom=12&size=640x280&maptype=mapnik&markers=${markers.join("|")}`;
    return { embedUrl, openUrl, staticUrl };
  }, [lat, lng, match.driver_lat, match.driver_lng, match.pickup, match.destination]);

  return (
    <View style={styles.wrap}>
      <View style={styles.mapBox}>
        {!iframeFailed
          ? createElement("iframe", {
              title: "Driver live map",
              src: embedUrl,
              style: {
                width: "100%",
                height: 240,
                border: 0,
                display: "block",
                borderRadius: 0,
              },
              onError: () => setIframeFailed(true),
            })
          : createElement("img", {
              src: staticUrl,
              alt: "Trip map",
              style: {
                width: "100%",
                height: 240,
                objectFit: "cover",
                display: "block",
              },
            })}
      </View>
      <View style={styles.meta}>
        <Text style={styles.title}>Driver map</Text>
        <Text style={styles.muted}>
          ETA pickup {fmtEta(match.eta_pickup)} · drop {fmtEta(match.eta_drop)}
        </Text>
        {match.driver_name ? (
          <Text style={styles.driver}>
            {match.driver_name}
            {match.vehicle_number ? ` · ${match.vehicle_number}` : ""}
          </Text>
        ) : null}
        {match.driver_lat != null && match.driver_lng != null ? (
          <Text style={styles.coords}>
            Driver @ {match.driver_lat.toFixed(4)}, {match.driver_lng.toFixed(4)}
          </Text>
        ) : null}
        {match.pickup && <LocLine label="Pickup" loc={match.pickup} />}
        {match.destination && <LocLine label="Drop" loc={match.destination} />}
        <Pressable onPress={() => void Linking.openURL(openUrl)}>
          <Text style={styles.link}>Open full map in new tab</Text>
        </Pressable>
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
  mapBox: {
    width: "100%",
    height: 240,
    backgroundColor: "#c5d4cf",
  },
  meta: { padding: 12, gap: 4 },
  title: { fontSize: 16, fontWeight: "700", color: "#0f3d38" },
  muted: { color: "#5a736e" },
  driver: { color: "#0f3d38", fontWeight: "600" },
  coords: { fontFamily: "monospace", color: "#0f3d38", fontSize: 12 },
  locLine: { color: "#0f3d38" },
  locLabel: { fontWeight: "600" },
  link: { marginTop: 6, color: "#1f8a7d", fontWeight: "600", textDecorationLine: "underline" },
});
