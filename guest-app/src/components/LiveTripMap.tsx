import { StyleSheet, Text, View } from "react-native";
import type { GuestLocation, GuestMatch } from "../types";

/**
 * Default / web implementation — must not import react-native-maps.
 * Native builds resolve LiveTripMap.native.tsx instead.
 */
export function LiveTripMap({ match }: { match: GuestMatch }) {
  const hasDriver = match.driver_lat != null && match.driver_lng != null;

  return (
    <View style={styles.fallback}>
      <Text style={styles.fallbackTitle}>Live tracking</Text>
      <Text style={styles.muted}>
        Driver ETA pickup {fmtEta(match.eta_pickup)} · drop {fmtEta(match.eta_drop)}
      </Text>
      {hasDriver && (
        <Text style={styles.coords}>
          Driver @ {match.driver_lat!.toFixed(4)}, {match.driver_lng!.toFixed(4)}
        </Text>
      )}
      {match.pickup && <LocLine label="Pickup" loc={match.pickup} />}
      {match.destination && <LocLine label="Drop" loc={match.destination} />}
      <Text style={styles.hint}>Interactive map is available in Expo Go on iOS/Android.</Text>
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
  fallback: {
    padding: 16,
    borderRadius: 16,
    backgroundColor: "#eef6f4",
    borderWidth: 1,
    borderColor: "#d5e0dc",
    gap: 6,
  },
  fallbackTitle: { fontSize: 16, fontWeight: "700", color: "#0f3d38" },
  muted: { color: "#5a736e" },
  coords: { fontFamily: "monospace", color: "#0f3d38" },
  hint: { marginTop: 8, color: "#8aa39d", fontSize: 12 },
  locLine: { color: "#0f3d38" },
  locLabel: { fontWeight: "600" },
});
