import type { AuthUser, GuestLocation, GuestMatch, GuestMe, RideRequest } from "../types";

/** Use EXPO_PUBLIC_API_BASE for a physical device (your LAN IP). */
const API_BASE = process.env.EXPO_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

function authHeaders(user: AuthUser | null): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (user?.role === "guest" && user.guest_id) {
    headers["X-Role"] = "guest";
    headers["X-Guest-Id"] = user.guest_id;
    headers["X-User-Id"] = user.user_id;
  }
  return headers;
}

async function request<T>(path: string, user: AuthUser | null, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(user), ...(init?.headers as Record<string, string> | undefined) },
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
  baseUrl: API_BASE,
  login: (email: string) =>
    request<AuthUser>("/auth/login", null, { method: "POST", body: JSON.stringify({ email }) }),
  me: (user: AuthUser) => request<GuestMe>("/guest/me", user),
  match: async (user: AuthUser) => {
    const body = await request<GuestMatch | null>("/guest/match", user);
    return body ?? null;
  },
  locations: (user: AuthUser) => request<GuestLocation[]>("/guest/locations", user),
  rideRequests: (user: AuthUser) => request<RideRequest[]>("/guest/ride-requests", user),
  requestRide: (
    user: AuthUser,
    body: {
      origin_location_id?: string;
      dest_location_id?: string;
      party_size?: number;
      luggage_count?: number;
    },
  ) =>
    request<RideRequest>("/guest/ride-requests", user, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
