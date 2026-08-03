import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    driver = "driver"
    guest = "guest"


class DriverStatus(str, enum.Enum):
    offline = "offline"
    available = "available"
    en_route = "en_route"
    at_pickup = "at_pickup"
    in_trip = "in_trip"
    on_break = "on_break"


class LocationType(str, enum.Enum):
    airport = "airport"
    station = "station"
    venue = "venue"
    hotel = "hotel"


class TripType(str, enum.Enum):
    arrival = "arrival"
    to_venue = "to_venue"
    from_venue = "from_venue"
    departure = "departure"
    on_demand = "on_demand"


class TripStatus(str, enum.Enum):
    planned = "planned"
    offered = "offered"
    accepted = "accepted"
    en_route = "en_route"
    at_pickup = "at_pickup"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class StopType(str, enum.Enum):
    pickup = "pickup"
    drop = "drop"


class AttendanceStatus(str, enum.Enum):
    expected = "expected"
    checked_in = "checked_in"
    no_show = "no_show"
    cancelled = "cancelled"


class RideRequestStatus(str, enum.Enum):
    pending_admin = "pending_admin"
    approved = "approved"
    queued = "queued"
    matched = "matched"
    declined = "declined"
    cancelled = "cancelled"


class AssignmentSource(str, enum.Enum):
    batch = "batch"
    greedy = "greedy"
    detour = "detour"
    override = "override"
    placeholder = "placeholder"


class MatchJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
