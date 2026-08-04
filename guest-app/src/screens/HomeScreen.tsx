import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { LiveTripMap } from "../components/LiveTripMap";
import type { GuestLocation, GuestMatch, GuestMe, RideRequest } from "../types";
import { registerGuestPush } from "../push";

type Tab = "home" | "ride" | "request";

function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function fmtEta(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function HomeScreen() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("home");
  const [me, setMe] = useState<GuestMe | null>(null);
  const [match, setMatch] = useState<GuestMatch | null>(null);
  const [requests, setRequests] = useState<RideRequest[]>([]);
  const [locations, setLocations] = useState<GuestLocation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [originId, setOriginId] = useState<string | null>(null);
  const [destId, setDestId] = useState<string | null>(null);
  const prevMatched = useRef<string | null>(null);

  const applyMatch = useCallback((mt: GuestMatch | null) => {
    // Normalize: ended / missing match clears the Ride tab
    const activeMatch =
      mt && mt.trip_status !== "completed" && mt.trip_status !== "cancelled" ? mt : null;
    setMatch(activeMatch);

    // Passive in-app notification when a new match appears (no browsing/choosing)
    if (activeMatch?.trip_id && prevMatched.current !== activeMatch.trip_id) {
      if (prevMatched.current !== null || activeMatch.matched) {
        setFlash(
          `Matched · ${activeMatch.driver_name} · ${activeMatch.vehicle_number ?? "vehicle"} · ETA ${fmtEta(activeMatch.eta_pickup)}`,
        );
        setTab("ride");
      }
      prevMatched.current = activeMatch.trip_id;
    } else if (!activeMatch) {
      if (prevMatched.current !== null) {
        setFlash("Ride completed — thanks for traveling with SmartDispatch.");
        setTab("home");
      }
      prevMatched.current = null;
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!user) return;
    // Match is fetched alone so a failure elsewhere cannot leave a stale "Your ride"
    try {
      const mt = await api.match(user);
      applyMatch(mt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load match");
    }
    try {
      const [m, rr, locs] = await Promise.all([
        api.me(user),
        api.rideRequests(user),
        api.locations(user),
      ]);
      setMe(m);
      setRequests(rr);
      setLocations(locs);
      if (!originId && m.pickup) setOriginId(m.pickup.id);
      if (!destId && m.accommodation) setDestId(m.accommodation.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [user, originId, destId, applyMatch]);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 6000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (user) void registerGuestPush(user);
  }, [user]);

  const pending = requests.find((r) => r.status === "pending_admin");

  async function submitRequest() {
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      await api.requestRide(user, {
        origin_location_id: originId ?? undefined,
        dest_location_id: destId ?? undefined,
        party_size: me?.party_size,
        luggage_count: me?.luggage_count,
      });
      setFlash("Ride request submitted — pending admin approval");
      setTab("request");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.shell}>
      <View style={styles.header}>
        <View>
          <Text style={styles.brand}>
            Smart<Text style={styles.brandAccent}>Dispatch</Text>
          </Text>
          <Text style={styles.hello}>{me?.full_name ?? user?.full_name}</Text>
        </View>
        <Pressable onPress={() => void logout()}>
          <Text style={styles.logout}>Sign out</Text>
        </Pressable>
      </View>

      {flash ? (
        <Pressable style={styles.banner} onPress={() => setFlash(null)}>
          <Text style={styles.bannerText}>{flash}</Text>
          <Text style={styles.bannerDismiss}>tap to dismiss</Text>
        </Pressable>
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {tab === "home" && me && (
          <View style={styles.stack}>
            <Text style={styles.h2}>Your pickup</Text>
            <View style={styles.block}>
              <Text style={styles.k}>Travel</Text>
              <Text style={styles.v}>
                {(me.travel_mode ?? "trip").toUpperCase()}
                {me.travel_ref ? ` ${me.travel_ref}` : ""}
              </Text>
              <Text style={styles.muted}>ETA {fmtWhen(me.travel_eta)}</Text>
            </View>
            <View style={styles.block}>
              <Text style={styles.k}>Pickup point</Text>
              <Text style={styles.v}>{me.pickup?.name ?? "Not set"}</Text>
              <Text style={styles.muted}>{me.pickup?.address}</Text>
            </View>
            <View style={styles.block}>
              <Text style={styles.k}>Accommodation</Text>
              <Text style={styles.v}>{me.accommodation?.name ?? "Not set"}</Text>
              <Text style={styles.muted}>{me.accommodation?.address}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.chip}>{me.party_size} guests</Text>
              <Text style={styles.chip}>{me.luggage_count} bags</Text>
              <Text style={styles.chip}>{me.attendance_status}</Text>
            </View>
            {!match && (
              <Text style={styles.muted}>
                You will be notified here once a driver is assigned — no need to browse or choose.
              </Text>
            )}
            {match && (
              <Pressable style={styles.primaryBtn} onPress={() => setTab("ride")}>
                <Text style={styles.primaryBtnText}>View your ride</Text>
              </Pressable>
            )}
          </View>
        )}

        {tab === "ride" && (
          <View style={styles.stack}>
            <Text style={styles.h2}>Your ride</Text>
            {!match ? (
              <View style={styles.block}>
                <Text style={styles.v}>No active ride</Text>
                <Text style={styles.muted}>
                  {pending
                    ? "Your on-demand request is pending admin approval. Matching starts after approval."
                    : "When dispatch assigns a driver, details appear here automatically. After drop-off, this screen clears."}
                </Text>
              </View>
            ) : (
              <>
                <View style={styles.matchCard}>
                  <Text style={styles.matchLabel}>Driver assigned</Text>
                  <Text style={styles.matchName}>{match.driver_name}</Text>
                  <Text style={styles.matchPlate}>{match.vehicle_number ?? "—"}</Text>
                  {match.vehicle_make_model ? (
                    <Text style={styles.muted}>{match.vehicle_make_model}</Text>
                  ) : null}
                  <View style={styles.etaRow}>
                    <View>
                      <Text style={styles.kOnDark}>Pickup ETA</Text>
                      <Text style={styles.etaBig}>{fmtEta(match.eta_pickup)}</Text>
                    </View>
                    <View>
                      <Text style={styles.kOnDark}>Status</Text>
                      <Text style={styles.statusOnDark}>{String(match.trip_status).replace(/_/g, " ")}</Text>
                    </View>
                  </View>
                </View>
                <LiveTripMap match={match} />
              </>
            )}
          </View>
        )}

        {tab === "request" && (
          <View style={styles.stack}>
            <Text style={styles.h2}>On-demand ride</Text>
            <Text style={styles.muted}>
              Submit a request for admin review. After approval, matching assigns a driver automatically
              — you never pick one.
            </Text>

            {pending ? (
              <View style={styles.pendingBox}>
                <Text style={styles.pendingTitle}>Request pending</Text>
                <Text style={styles.muted}>
                  Submitted {fmtWhen(pending.created_at)}. Waiting for operations to approve.
                </Text>
              </View>
            ) : (
              <>
                <Text style={styles.k}>From</Text>
                <LocPicker
                  locations={locations}
                  value={originId}
                  onChange={setOriginId}
                />
                <Text style={styles.k}>To</Text>
                <LocPicker locations={locations} value={destId} onChange={setDestId} />
                <Pressable
                  style={[styles.primaryBtn, busy && { opacity: 0.7 }]}
                  disabled={busy || !originId || !destId}
                  onPress={() => void submitRequest()}
                >
                  {busy ? (
                    <ActivityIndicator color="#06241f" />
                  ) : (
                    <Text style={styles.primaryBtnText}>Request ride</Text>
                  )}
                </Pressable>
              </>
            )}

            {requests.length > 0 && (
              <View style={styles.stack}>
                <Text style={styles.k}>Your requests</Text>
                {requests.slice(0, 5).map((r) => (
                  <View key={r.id} style={styles.reqRow}>
                    <Text style={styles.v}>{r.status.replace("_", " ")}</Text>
                    <Text style={styles.muted}>{fmtWhen(r.created_at)}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {!me && !error ? (
          <ActivityIndicator color="#2bb3a3" style={{ marginTop: 40 }} />
        ) : null}
      </ScrollView>

      <View style={styles.tabs}>
        {(
          [
            ["home", "Pickup"],
            ["ride", "Ride"],
            ["request", "Request"],
          ] as const
        ).map(([id, label]) => (
          <Pressable key={id} style={[styles.tab, tab === id && styles.tabOn]} onPress={() => setTab(id)}>
            <Text style={[styles.tabText, tab === id && styles.tabTextOn]}>{label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function LocPicker({
  locations,
  value,
  onChange,
}: {
  locations: GuestLocation[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <View style={styles.picker}>
      {locations.map((loc) => {
        const on = loc.id === value;
        return (
          <Pressable
            key={loc.id}
            style={[styles.pickItem, on && styles.pickItemOn]}
            onPress={() => onChange(loc.id)}
          >
            <Text style={[styles.pickTitle, on && styles.pickTitleOn]}>{loc.name}</Text>
            <Text style={styles.pickSub}>{loc.type}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: "#f3f7f6" },
  header: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 12,
    backgroundColor: "#0f3d38",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  brand: { fontSize: 22, fontWeight: "800", color: "#fff" },
  brandAccent: { color: "#2bb3a3" },
  hello: { color: "#9ec9c2", marginTop: 2 },
  logout: { color: "#c5e4de", fontWeight: "600", marginTop: 4 },
  banner: {
    backgroundColor: "#1f8a7d",
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bannerText: { color: "#fff", fontWeight: "700" },
  bannerDismiss: { color: "#c5e4de", fontSize: 11, marginTop: 2 },
  error: {
    margin: 12,
    padding: 10,
    backgroundColor: "#fde8e8",
    color: "#a33",
    borderRadius: 10,
    overflow: "hidden",
  },
  content: { padding: 20, paddingBottom: 100 },
  stack: { gap: 14 },
  h2: { fontSize: 24, fontWeight: "800", color: "#0f3d38" },
  block: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#dce8e4",
    gap: 4,
  },
  k: { color: "#5a736e", fontSize: 12, fontWeight: "600", textTransform: "uppercase" },
  v: { color: "#0f3d38", fontSize: 17, fontWeight: "700" },
  muted: { color: "#5a736e", lineHeight: 20 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: "#e7f3f0",
    color: "#0f3d38",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    overflow: "hidden",
    fontSize: 13,
    fontWeight: "600",
  },
  primaryBtn: {
    backgroundColor: "#2bb3a3",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryBtnText: { color: "#06241f", fontWeight: "700", fontSize: 16 },
  matchCard: {
    backgroundColor: "#0f3d38",
    borderRadius: 16,
    padding: 16,
    gap: 4,
  },
  matchLabel: { color: "#9ec9c2", fontSize: 12, fontWeight: "600" },
  matchName: { color: "#fff", fontSize: 26, fontWeight: "800" },
  matchPlate: { color: "#2bb3a3", fontSize: 20, fontWeight: "700", letterSpacing: 1 },
  etaRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 12 },
  etaBig: { color: "#fff", fontSize: 28, fontWeight: "800" },
  kOnDark: { color: "#9ec9c2", fontSize: 12, fontWeight: "600", textTransform: "uppercase" },
  statusOnDark: { color: "#fff", fontSize: 17, fontWeight: "700", textTransform: "capitalize" },
  pendingBox: {
    backgroundColor: "#fff7e8",
    borderColor: "#e6a23c",
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    gap: 6,
  },
  pendingTitle: { color: "#8a5a10", fontWeight: "800", fontSize: 18 },
  picker: { gap: 8 },
  pickItem: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "#dce8e4",
  },
  pickItemOn: { borderColor: "#2bb3a3", backgroundColor: "#e7f3f0" },
  pickTitle: { color: "#0f3d38", fontWeight: "700" },
  pickTitleOn: { color: "#0f3d38" },
  pickSub: { color: "#5a736e", fontSize: 12 },
  reqRow: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: "#dce8e4",
  },
  tabs: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 24,
    flexDirection: "row",
    backgroundColor: "#0f3d38",
    borderRadius: 16,
    padding: 4,
  },
  tab: { flex: 1, paddingVertical: 12, alignItems: "center", borderRadius: 12 },
  tabOn: { backgroundColor: "#1f8a7d" },
  tabText: { color: "#9ec9c2", fontWeight: "600" },
  tabTextOn: { color: "#fff" },
});
