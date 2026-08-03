import { StyleSheet, Text, View } from "react-native";
import MapView, { Marker, PROVIDER_DEFAULT } from "react-native-maps";
import type { GuestMatch } from "../types";

function fmtEta(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function LiveTripMap({ match }: { match: GuestMatch }) {
  const pickup = match.pickup;
  const dest = match.destination;
  const hasDriver = match.driver_lat != null && match.driver_lng != null;
  const centerLat = match.driver_lat ?? pickup?.lat ?? dest?.lat ?? 28.6139;
  const centerLng = match.driver_lng ?? pickup?.lng ?? dest?.lng ?? 77.209;

  return (
    <View style={styles.mapWrap}>
      <MapView
        style={styles.map}
        provider={PROVIDER_DEFAULT}
        initialRegion={{
          latitude: centerLat,
          longitude: centerLng,
          latitudeDelta: 0.08,
          longitudeDelta: 0.08,
        }}
        region={{
          latitude: centerLat,
          longitude: centerLng,
          latitudeDelta: 0.08,
          longitudeDelta: 0.08,
        }}
      >
        {hasDriver && (
          <Marker
            coordinate={{ latitude: match.driver_lat!, longitude: match.driver_lng! }}
            title={match.driver_name}
            description={match.vehicle_number ?? "Your vehicle"}
            pinColor="#1f8a7d"
          />
        )}
        {pickup && (
          <Marker
            coordinate={{ latitude: pickup.lat, longitude: pickup.lng }}
            title="Pickup"
            description={pickup.name}
            pinColor="#e6a23c"
          />
        )}
        {dest && (
          <Marker
            coordinate={{ latitude: dest.lat, longitude: dest.lng }}
            title="Destination"
            description={dest.name}
            pinColor="#5b9fd6"
          />
        )}
      </MapView>
      <View style={styles.etaChip}>
        <Text style={styles.etaLabel}>ETA pickup</Text>
        <Text style={styles.etaValue}>{fmtEta(match.eta_pickup)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  mapWrap: {
    height: 280,
    borderRadius: 16,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#d5e0dc",
  },
  map: { flex: 1 },
  etaChip: {
    position: "absolute",
    top: 12,
    right: 12,
    backgroundColor: "rgba(15, 61, 56, 0.92)",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  etaLabel: { color: "#9ec9c2", fontSize: 11 },
  etaValue: { color: "#fff", fontSize: 18, fontWeight: "700" },
});
