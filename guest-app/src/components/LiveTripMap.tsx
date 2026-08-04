import { useMemo } from "react";
import { Image, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import type { GuestLocation, GuestMatch } from "../types";

/**
 * Default / web map — used on web and as fallback.
 * Native (iOS/Android) resolves LiveTripMap.native.tsx instead (react-native-maps).
 *
 * Uses a static OSM image (no iframe / X-Frame issues on Vercel).
 */
export function LiveTripMap({ match }: { match: GuestMatch }) {
  const lat = match.driver_lat ?? match.pickup?.lat ?? match.destination?.lat ?? 28.6139;
  const lng = match.driver_lng ?? match.pickup?.lng ?? match.destination?.lng ?? 77.209;

  const { imageUrl, openUrl } = useMemo(() => {
    const markers: string[] = [];
    if (match.driver_lat != null && match.driver_lng != null) {
      markers.push(`${match.driver_lat},${match.driver_lng},red-pushpin`);
    }
    if (match.pickup) {
      markers.push(`${match.pickup.lat},${match.pickup.lng},orange-pushpin`);
    }
    if (match.destination) {
      markers.push(`${match.destination.lat},${match.destination.lng},green-pushpin`);
    }
    if (markers.length === 0) {
      markers.push(`${lat},${lng},lightblue1`);
    }
    const markerParam = markers.join("|");
    const imageUrl =
      `https://staticmap.openstreetmap.de/staticmap.php` +
      `?center=${lat},${lng}&zoom=13&size=640x280&maptype=mapnik&markers=${markerParam}`;
    const openUrl =
      `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=14/${lat}/${lng}`;
    return { imageUrl, openUrl };
  }, [lat, lng, match.driver_lat, match.driver_lng, match.pickup, match.destination]);

  return (
    <View style={styles.wrap}>
      <Pressable onPress={() => void Linking.openURL(openUrl)} accessibilityRole="link">
        <Image source={{ uri: imageUrl }} style={styles.map} resizeMode="cover" />
      </Pressable>
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
        <Text style={styles.legend}>Red = driver · Orange = pickup · Green = drop · tap map to open</Text>
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
  map: {
    width: "100%",
    height: 220,
    backgroundColor: "#d5e0dc",
  },
  meta: { padding: 12, gap: 4 },
  title: { fontSize: 16, fontWeight: "700", color: "#0f3d38" },
  muted: { color: "#5a736e" },
  driver: { color: "#0f3d38", fontWeight: "600" },
  legend: { color: "#8aa39d", fontSize: 11, marginTop: 2 },
  locLine: { color: "#0f3d38" },
  locLabel: { fontWeight: "600" },
});
