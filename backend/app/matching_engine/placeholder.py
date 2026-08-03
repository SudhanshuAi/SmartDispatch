"""Backward-compatible shim — real engine is DispatchMatchingEngine. """

from app.matching_engine.engine import DispatchMatchingEngine
from app.matching_engine.types import DriverSnapshot, GuestSnapshot, MatchOneResult

# Re-export old names used by Phase-1 trip_service during transition
from app.matching_engine.greedy import match_one as _match_one
from app.matching_engine.types import GeoPoint
from datetime import datetime
from uuid import UUID


class PlaceholderMatchingEngine:
    """Deprecated: wraps greedy match_one for old call sites."""

    def match_one(self, request, candidates):  # noqa: ANN001
        from app.matching_engine.types import GuestSnapshot as GS

        now = datetime.utcnow().replace(tzinfo=None)
        # Minimal adapter — prefer DispatchMatchingEngine in new code
        guest = GS(
            guest_id=request.guest_id,
            party_size=request.party_size,
            luggage_count=request.luggage_count,
            pickup_location_id=request.origin_location_id,
            drop_location_id=request.dest_location_id,
            ready_at=request.pickup_by or now,
            priority=request.priority,
        )
        drivers = [
            DriverSnapshot(
                driver_id=c.driver_id,
                vehicle_id=c.vehicle_id,
                seat_capacity=c.seat_capacity,
                luggage_capacity=c.luggage_capacity,
                status=c.status,
                break_until=c.break_until,
                live_position=GeoPoint(0.0, 0.0),
                predicted_free_at=None,
                predicted_free_position=None,
                depot=GeoPoint(0.0, 0.0),
            )
            for c in candidates
        ]
        locs = {
            request.origin_location_id: GeoPoint(0.0, 0.0),
            request.dest_location_id: GeoPoint(0.01, 0.01),
        }
        return _match_one(guest, drivers, locs, now=now)
