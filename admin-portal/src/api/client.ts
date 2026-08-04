import type {
  AuthUser,
  DashboardSnapshot,
  Driver,
  DriverMe,
  DriverTrip,
  Guest,
  Location,
  RideRequest,
  Trip,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

function authHeaders(): HeadersInit {
  const raw = localStorage.getItem("sd_auth");
  const user = raw ? (JSON.parse(raw) as AuthUser) : null;
  const role = user?.role === "driver" ? "driver" : "admin";
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Role": role,
  };
  if (user?.role === "driver" && user.driver_id) {
    headers["X-Driver-Id"] = user.driver_id;
    headers["X-User-Id"] = user.user_id;
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  login: (email: string) =>
    request<AuthUser>("/auth/login", { method: "POST", body: JSON.stringify({ email }) }),
  dashboard: () => request<DashboardSnapshot>("/admin/dashboard"),
  locations: () => request<Location[]>("/admin/locations"),
  drivers: () => request<Driver[]>("/admin/drivers"),
  guests: () => request<Guest[]>("/admin/guests"),
  trips: () => request<Trip[]>("/admin/trips"),
  rideRequests: (status?: string) =>
    request<RideRequest[]>(status ? `/admin/ride-requests?status=${status}` : "/admin/ride-requests"),
  seedRideRequests: () => request<RideRequest[]>("/admin/ride-requests/seed-demo?n=5", { method: "POST" }),
  approveRequest: (id: string) =>
    request<{ status: string; message: string }>(`/admin/ride-requests/${id}/approve`, { method: "POST" }),
  declineRequest: (id: string) => request(`/admin/ride-requests/${id}/decline`, { method: "POST" }),
  onboardDriver: (body: Record<string, unknown>) =>
    request("/admin/drivers/onboard", { method: "POST", body: JSON.stringify(body) }),
  updateGuest: (id: string, body: Record<string, unknown>) =>
    request(`/admin/guests/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  walkInGuest: (body: Record<string, unknown>) =>
    request("/admin/guests/walk-in", { method: "POST", body: JSON.stringify(body) }),
  updateDriver: (id: string, body: Record<string, unknown>) =>
    request(`/admin/drivers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  reassign: (body: Record<string, unknown>) =>
    request("/admin/override/reassign", { method: "POST", body: JSON.stringify(body) }),
  vehicleDown: (body: Record<string, unknown>) =>
    request("/admin/override/vehicle-down", { method: "POST", body: JSON.stringify(body) }),
  forceMatch: (body: Record<string, unknown>) =>
    request("/admin/override/force-match", { method: "POST", body: JSON.stringify(body) }),
  runBatch: () => request("/admin/matching/batch", { method: "POST" }),
  processQueue: () =>
    request<{
      processed: boolean;
      reason?: string;
      skipped_stale?: number;
      queue_depth?: number;
    }>("/admin/matching/queue/process", { method: "POST" }),
  clearQueue: () =>
    request<{ cleared: number; queue_depth: number }>("/admin/matching/queue/clear", { method: "POST" }),
  matchingStatus: () =>
    request<{ queue_depth: number; matching_engine_enabled: boolean }>("/admin/matching/status"),

  driverMe: () => request<DriverMe>("/driver/me"),
  driverTrip: async () => {
    const res = await fetch(`${API_BASE}/driver/trip`, { headers: authHeaders() });
    if (res.status === 204 || res.status === 404) return null;
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    const body = await res.json();
    return (body ?? null) as DriverTrip | null;
  },
  driverAccept: () => request<DriverTrip>("/driver/trip/accept", { method: "POST" }),
  driverReject: (reason?: string) =>
    request<{ rejected: boolean }>("/driver/trip/reject", {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  driverStatus: (action: "arrived_pickup" | "boarded" | "arrived_drop") =>
    request<DriverTrip>("/driver/trip/status", {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  driverLocation: (body: { lat: number; lng: number; heading?: number; speed?: number }) =>
    request("/driver/location", { method: "POST", body: JSON.stringify(body) }),
  driverEndBreak: () => request<DriverMe>("/driver/break/end", { method: "POST" }),
};
