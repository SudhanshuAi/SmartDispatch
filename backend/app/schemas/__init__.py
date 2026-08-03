from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AttendanceStatus,
    DriverStatus,
    LocationType,
    RideRequestStatus,
    TripStatus,
    TripType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----- Vehicle -----


class VehicleCreate(BaseModel):
    plate_number: str
    seat_capacity: int = Field(ge=1, le=50)
    luggage_capacity: int = Field(ge=0, le=50)
    make_model: str | None = None


class VehicleUpdate(BaseModel):
    plate_number: str | None = None
    seat_capacity: int | None = Field(default=None, ge=1, le=50)
    luggage_capacity: int | None = Field(default=None, ge=0, le=50)
    make_model: str | None = None


class VehicleRead(ORMModel):
    id: UUID
    plate_number: str
    seat_capacity: int
    luggage_capacity: int
    make_model: str | None
    created_at: datetime


# ----- Driver -----


class DriverCreate(BaseModel):
    email: str
    full_name: str
    phone: str | None = None
    password: str = "changeme"
    vehicle_id: UUID
    status: DriverStatus = DriverStatus.available
    last_lat: float | None = None
    last_lng: float | None = None


class DriverUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    vehicle_id: UUID | None = None
    status: DriverStatus | None = None
    break_until: datetime | None = None
    predicted_free_at: datetime | None = None
    predicted_free_lat: float | None = None
    predicted_free_lng: float | None = None
    last_lat: float | None = None
    last_lng: float | None = None


class DriverRead(ORMModel):
    id: UUID
    user_id: UUID
    vehicle_id: UUID
    status: DriverStatus
    break_until: datetime | None
    predicted_free_at: datetime | None
    predicted_free_lat: float | None
    predicted_free_lng: float | None
    last_lat: float | None
    last_lng: float | None
    created_at: datetime
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    vehicle: VehicleRead | None = None


# ----- Guest -----


class GuestCreate(BaseModel):
    email: str
    full_name: str
    phone: str | None = None
    password: str = "changeme"
    party_size: int = Field(default=1, ge=1, le=20)
    luggage_count: int = Field(default=0, ge=0, le=50)
    travel_eta: datetime | None = None
    travel_mode: str | None = None
    travel_ref: str | None = None
    pickup_location_id: UUID | None = None
    accommodation_id: UUID | None = None
    priority: bool = False
    attendance_status: AttendanceStatus = AttendanceStatus.expected


class GuestUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    luggage_count: int | None = Field(default=None, ge=0, le=50)
    travel_eta: datetime | None = None
    travel_mode: str | None = None
    travel_ref: str | None = None
    pickup_location_id: UUID | None = None
    accommodation_id: UUID | None = None
    priority: bool | None = None
    attendance_status: AttendanceStatus | None = None


class GuestRead(ORMModel):
    id: UUID
    user_id: UUID
    party_size: int
    luggage_count: int
    travel_eta: datetime | None
    travel_mode: str | None
    travel_ref: str | None
    pickup_location_id: UUID | None
    accommodation_id: UUID | None
    priority: bool
    attendance_status: AttendanceStatus
    created_at: datetime
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None


# ----- Trip -----


class TripCreate(BaseModel):
    trip_type: TripType
    status: TripStatus = TripStatus.planned
    driver_id: UUID | None = None
    origin_location_id: UUID | None = None
    dest_location_id: UUID | None = None
    scheduled_pickup_at: datetime | None = None
    scheduled_drop_at: datetime | None = None
    eta_pickup: datetime | None = None
    eta_drop: datetime | None = None
    seats_used: int = 0
    luggage_used: int = 0
    guest_ids: list[UUID] = Field(default_factory=list)
    notes: str | None = None


class TripUpdate(BaseModel):
    status: TripStatus | None = None
    driver_id: UUID | None = None
    origin_location_id: UUID | None = None
    dest_location_id: UUID | None = None
    scheduled_pickup_at: datetime | None = None
    scheduled_drop_at: datetime | None = None
    eta_pickup: datetime | None = None
    eta_drop: datetime | None = None
    seats_used: int | None = None
    luggage_used: int | None = None
    notes: str | None = None
    route_version: int | None = None  # required for optimistic-lock updates when set


class TripRead(ORMModel):
    id: UUID
    trip_type: TripType
    status: TripStatus
    driver_id: UUID | None
    origin_location_id: UUID | None
    dest_location_id: UUID | None
    scheduled_pickup_at: datetime | None
    scheduled_drop_at: datetime | None
    eta_pickup: datetime | None
    eta_drop: datetime | None
    seats_used: int
    luggage_used: int
    route_version: int
    party_group_id: UUID | None
    notes: str | None
    created_at: datetime
    guest_ids: list[UUID] = Field(default_factory=list)


class MatchGuestRequest(BaseModel):
    """Admin trigger: run matcher for a guest arrival transfer."""

    guest_id: UUID


# ----- Locations / Ride requests / Ops -----


class LocationRead(ORMModel):
    id: UUID
    name: str
    type: LocationType
    address: str
    lat: float
    lng: float


class RideRequestCreate(BaseModel):
    guest_id: UUID
    origin_location_id: UUID | None = None
    dest_location_id: UUID | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    luggage_count: int | None = Field(default=None, ge=0, le=50)


class RideRequestRead(ORMModel):
    id: UUID
    guest_id: UUID
    guest_name: str | None = None
    origin_location_id: UUID
    dest_location_id: UUID
    party_size: int
    luggage_count: int
    status: RideRequestStatus
    wait_started_at: datetime
    priority_score: float
    trip_id: UUID | None
    created_at: datetime


class DriverOnboardRequest(BaseModel):
    email: str
    full_name: str
    phone: str | None = None
    password: str = "driver"
    plate_number: str
    seat_capacity: int = Field(ge=1, le=50)
    luggage_capacity: int = Field(ge=0, le=50)
    make_model: str | None = None
    last_lat: float | None = 28.6139
    last_lng: float | None = 77.2090


class ReassignTripRequest(BaseModel):
    trip_id: UUID
    new_driver_id: UUID
    expected_route_version: int | None = None
    reason: str | None = None


class MarkVehicleDownRequest(BaseModel):
    driver_id: UUID
    reason: str | None = None


class ForceMatchRequest(BaseModel):
    guest_id: UUID
    driver_id: UUID
    reason: str | None = None


class LoginRequest(BaseModel):
    email: str


class DriverDashboardRow(BaseModel):
    driver: DriverRead
    current_trip: TripRead | None = None


class GuestDashboardRow(BaseModel):
    guest: GuestRead
    state: str


class DashboardSnapshot(BaseModel):
    drivers: list[DriverDashboardRow]
    guests: list[GuestDashboardRow]
    pending_ride_requests: list[RideRequestRead]
    active_trips: list[TripRead]
    counts: dict[str, int]


# ----- Driver portal -----


class GuestTripInfo(BaseModel):
    guest_id: UUID
    name: str
    party_size: int
    luggage_count: int
    boarded_at: datetime | None = None


class DriverTripView(BaseModel):
    trip_id: UUID
    status: TripStatus
    trip_type: TripType
    pickup_name: str | None = None
    pickup_address: str | None = None
    pickup_lat: float | None = None
    pickup_lng: float | None = None
    dest_name: str | None = None
    dest_address: str | None = None
    dest_lat: float | None = None
    dest_lng: float | None = None
    eta_pickup: datetime | None = None
    eta_drop: datetime | None = None
    scheduled_pickup_at: datetime | None = None
    guests: list[GuestTripInfo] = []
    seats_used: int = 0
    luggage_used: int = 0
    route_version: int = 1
    notes: str | None = None


class DriverMeRead(BaseModel):
    driver_id: UUID
    full_name: str
    phone: str | None = None
    status: DriverStatus
    plate_number: str | None = None
    seat_capacity: int | None = None
    luggage_capacity: int | None = None
    break_until: datetime | None = None
    on_break: bool = False
    break_remaining_seconds: int | None = None
    predicted_free_at: datetime | None = None
    last_lat: float | None = None
    last_lng: float | None = None
    mandatory_break_minutes: int = 10


class DriverLocationUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    heading: float | None = None
    speed: float | None = None


class DriverTripStatusUpdate(BaseModel):
    action: str  # arrived_pickup | boarded | arrived_drop


class DriverRejectRequest(BaseModel):
    reason: str | None = None


# ----- Guest portal -----


class GuestLocationRead(BaseModel):
    id: UUID
    name: str
    type: LocationType
    address: str
    lat: float
    lng: float


class GuestMeRead(BaseModel):
    guest_id: UUID
    full_name: str
    email: str | None = None
    phone: str | None = None
    party_size: int
    luggage_count: int
    travel_eta: datetime | None = None
    travel_mode: str | None = None
    travel_ref: str | None = None
    attendance_status: AttendanceStatus
    pickup: GuestLocationRead | None = None
    accommodation: GuestLocationRead | None = None


class GuestMatchView(BaseModel):
    matched: bool = True
    trip_id: UUID
    trip_status: TripStatus
    trip_type: TripType
    driver_name: str
    vehicle_number: str | None = None
    vehicle_make_model: str | None = None
    eta_pickup: datetime | None = None
    eta_drop: datetime | None = None
    driver_lat: float | None = None
    driver_lng: float | None = None
    pickup: GuestLocationRead | None = None
    destination: GuestLocationRead | None = None
    route_version: int = 1
    notified_at: datetime | None = None


class GuestRideRequestCreate(BaseModel):
    origin_location_id: UUID | None = None
    dest_location_id: UUID | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    luggage_count: int | None = Field(default=None, ge=0, le=50)
