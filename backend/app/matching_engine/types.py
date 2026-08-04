"""Pure matching-engine types. No DB / HTTP imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class UnmatchedReason(str, Enum):
    no_feasible_driver = "no_feasible_driver"
    no_capacity = "no_capacity"
    infeasible_eta = "infeasible_eta"
    needs_escalation = "needs_escalation"
    driver_offline = "driver_offline"
    version_conflict = "version_conflict"
    at_pickup_excluded = "at_pickup_excluded"


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float


@dataclass(frozen=True)
class LocationSnapshot:
    location_id: UUID
    lat: float
    lng: float
    name: str = ""


@dataclass(frozen=True)
class GuestSnapshot:
    guest_id: UUID
    party_size: int
    luggage_count: int
    pickup_location_id: UUID
    drop_location_id: UUID
    ready_at: datetime
    deadline_at: datetime | None = None
    priority: bool = False
    # After split: parent link
    party_group_id: UUID | None = None
    split_index: int | None = None


@dataclass(frozen=True)
class StopSnapshot:
    location_id: UUID
    lat: float
    lng: float
    stop_type: str  # pickup | drop
    guest_id: UUID | None
    sequence: int
    deadline_at: datetime | None = None
    completed: bool = False


@dataclass(frozen=True)
class ActiveTripSnapshot:
    trip_id: UUID
    route_version: int
    seats_used: int
    luggage_used: int
    trip_type: str
    stops: tuple[StopSnapshot, ...]
    locked_by_override: bool = False


@dataclass(frozen=True)
class DriverSnapshot:
    driver_id: UUID
    vehicle_id: UUID
    seat_capacity: int
    luggage_capacity: int
    status: str
    break_until: datetime | None
    live_position: GeoPoint | None
    predicted_free_at: datetime | None
    predicted_free_position: GeoPoint | None
    depot: GeoPoint
    current_trip: ActiveTripSnapshot | None = None
    cool_down_until: datetime | None = None


@dataclass(frozen=True)
class ProposedStop:
    location_id: UUID
    stop_type: str
    guest_id: UUID | None
    sequence: int
    deadline_at: datetime | None
    eta_at: datetime | None = None


@dataclass(frozen=True)
class ProposedTrip:
    driver_id: UUID
    vehicle_id: UUID
    guest_ids: tuple[UUID, ...]
    origin_location_id: UUID
    dest_location_id: UUID
    trip_type: str
    seats_used: int
    luggage_used: int
    scheduled_pickup_at: datetime | None
    eta_pickup: datetime | None
    eta_drop: datetime | None
    stops: tuple[ProposedStop, ...]
    party_group_id: UUID | None = None
    source: str = "greedy"
    # For detour apply:
    existing_trip_id: UUID | None = None
    expected_route_version: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class UnmatchedGuest:
    guest_id: UUID
    reason: UnmatchedReason
    detail: str = ""


@dataclass(frozen=True)
class BatchResult:
    trips: tuple[ProposedTrip, ...]
    unmatched: tuple[UnmatchedGuest, ...]
    splits: tuple[GuestSnapshot, ...] = ()  # synthetic split guests created


@dataclass(frozen=True)
class MatchOneResult:
    matched: bool
    trip: ProposedTrip | None = None
    trips: tuple[ProposedTrip, ...] = ()  # multi-trip when party is split
    unmatched: UnmatchedGuest | None = None
    # If detour was chosen:
    is_detour: bool = False

    def all_trips(self) -> tuple[ProposedTrip, ...]:
        if self.trips:
            return self.trips
        if self.trip is not None:
            return (self.trip,)
        return ()


@dataclass(frozen=True)
class DetourResult:
    accepted: bool
    trip: ProposedTrip | None = None
    reason: str = ""
    added_minutes: float = 0.0


@dataclass(frozen=True)
class ReoptTripInput:
    trip_id: UUID
    driver_id: UUID
    route_version: int
    needs_eta_refresh: bool
    current_eta_drop: datetime | None
    guest_deadlines: tuple[datetime | None, ...]
    boarded_guest_ids: tuple[UUID, ...]
    stops: tuple[StopSnapshot, ...]
    live_position: GeoPoint
    seats_used: int
    luggage_used: int
    current_eta_pickup: datetime | None = None
    # Floor for pickup ETA (guest travel_eta / scheduled) — prevents jumping earlier than the plan
    pickup_ready_at: datetime | None = None


@dataclass(frozen=True)
class ReoptAction:
    trip_id: UUID
    action: str  # refresh_eta | rematch | none
    new_eta_pickup: datetime | None = None
    new_eta_drop: datetime | None = None
    drift_minutes: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class ReoptResult:
    actions: tuple[ReoptAction, ...]
    matrix_calls: int
    cache_hits: int


@dataclass
class QueueItem:
    request_id: str
    guest_id: UUID
    party_size: int
    luggage_count: int
    origin_location_id: UUID
    dest_location_id: UUID
    wait_started_at: datetime
    deadline_at: datetime | None = None
    priority: bool = False
    score: float = 0.0
