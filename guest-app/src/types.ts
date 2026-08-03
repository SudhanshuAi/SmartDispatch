export type Role = "admin" | "driver" | "guest";

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  driver_id: string | null;
  guest_id: string | null;
  token: string;
}

export interface GuestLocation {
  id: string;
  name: string;
  type: string;
  address: string;
  lat: number;
  lng: number;
}

export interface GuestMe {
  guest_id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  party_size: number;
  luggage_count: number;
  travel_eta: string | null;
  travel_mode: string | null;
  travel_ref: string | null;
  attendance_status: string;
  pickup: GuestLocation | null;
  accommodation: GuestLocation | null;
}

export interface GuestMatch {
  matched: boolean;
  trip_id: string;
  trip_status: string;
  trip_type: string;
  driver_name: string;
  vehicle_number: string | null;
  vehicle_make_model: string | null;
  eta_pickup: string | null;
  eta_drop: string | null;
  driver_lat: number | null;
  driver_lng: number | null;
  pickup: GuestLocation | null;
  destination: GuestLocation | null;
  route_version: number;
  notified_at: string | null;
}

export interface RideRequest {
  id: string;
  guest_id: string;
  guest_name: string | null;
  origin_location_id: string;
  dest_location_id: string;
  party_size: number;
  luggage_count: number;
  status: string;
  wait_started_at: string;
  trip_id: string | null;
  created_at: string;
}
