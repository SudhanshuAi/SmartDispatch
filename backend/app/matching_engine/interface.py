from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class MatchRequest:
    """Input snapshot for a single greedy / placeholder match."""

    guest_id: UUID
    party_size: int
    luggage_count: int
    origin_location_id: UUID
    dest_location_id: UUID
    pickup_by: datetime | None = None
    priority: bool = False


@dataclass(frozen=True)
class MatchResult:
    """Proposed assignment — API/services apply it; engine does not write DB."""

    guest_id: UUID
    driver_id: UUID | None
    vehicle_id: UUID | None
    reason: str
    matched: bool


@dataclass(frozen=True)
class DriverCandidate:
    driver_id: UUID
    vehicle_id: UUID
    seat_capacity: int
    luggage_capacity: int
    status: str
    break_until: datetime | None
    seats_already_used: int = 0
    luggage_already_used: int = 0


class MatchingEngine(Protocol):
    def match_one(self, request: MatchRequest, candidates: list[DriverCandidate]) -> MatchResult:
        """Pick a driver for one request. Must not touch the database."""
        ...
