export type Role = "admin" | "driver" | "guest";

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  driver_id: string | null;
  guest_id?: string | null;
  token: string;
}

export interface Vehicle {
  id: string;
  plate_number: string;
  seat_capacity: number;
  luggage_capacity: number;
  make_model: string | null;
}

export interface Driver {
  id: string;
  user_id: string;
  vehicle_id: string;
  status: string;
  break_until: string | null;
  last_lat: number | null;
  last_lng: number | null;
  email?: string | null;
  full_name?: string | null;
  phone?: string | null;
  vehicle?: Vehicle | null;
}

export interface Guest {
  id: string;
  user_id: string;
  party_size: number;
  luggage_count: number;
  travel_eta: string | null;
  travel_mode: string | null;
  travel_ref: string | null;
  pickup_location_id: string | null;
  accommodation_id: string | null;
  priority: boolean;
  attendance_status: string;
  email?: string | null;
  full_name?: string | null;
  phone?: string | null;
}

export interface Trip {
  id: string;
  trip_type: string;
  status: string;
  driver_id: string | null;
  origin_location_id: string | null;
  dest_location_id: string | null;
  seats_used: number;
  luggage_used: number;
  route_version: number;
  eta_pickup: string | null;
  eta_drop: string | null;
  notes: string | null;
  guest_ids: string[];
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

export interface Location {
  id: string;
  name: string;
  type: string;
  address: string;
  lat: number;
  lng: number;
}

export interface DashboardSnapshot {
  drivers: { driver: Driver; current_trip: Trip | null }[];
  guests: { guest: Guest; state: string }[];
  pending_ride_requests: RideRequest[];
  active_trips: Trip[];
  counts: Record<string, number>;
}

/** Driver-portal trip payload from GET /driver/trip */
export interface DriverGuestInfo {
  guest_id: string;
  name: string;
  party_size: number;
  luggage_count: number;
  boarded_at: string | null;
}

export interface DriverTrip {
  trip_id: string;
  status: string;
  trip_type: string;
  pickup_name: string | null;
  pickup_address: string | null;
  pickup_lat: number | null;
  pickup_lng: number | null;
  dest_name: string | null;
  dest_address: string | null;
  dest_lat: number | null;
  dest_lng: number | null;
  eta_pickup: string | null;
  eta_drop: string | null;
  scheduled_pickup_at: string | null;
  guests: DriverGuestInfo[];
  seats_used: number;
  luggage_used: number;
  route_version: number;
  notes: string | null;
}

/** Driver-portal profile from GET /driver/me */
export interface DriverMe {
  driver_id: string;
  full_name: string;
  phone: string | null;
  status: string;
  plate_number: string | null;
  seat_capacity: number | null;
  luggage_capacity: number | null;
  break_until: string | null;
  on_break: boolean;
  break_remaining_seconds: number | null;
  predicted_free_at: string | null;
  last_lat: number | null;
  last_lng: number | null;
  mandatory_break_minutes: number;
}
