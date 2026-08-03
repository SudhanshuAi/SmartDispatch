"""Opportunistic detour insertion using live driver position."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.constants import MAX_DETOUR_INSERTION_MINUTES
from app.matching_engine.capacity import can_accept
from app.matching_engine.routing import CachedTravelProvider, TravelTimeProvider
from app.matching_engine.types import (
    DetourResult,
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    ProposedStop,
    ProposedTrip,
    StopSnapshot,
)


def try_detour(
    driver: DriverSnapshot,
    guest: GuestSnapshot,
    locations: dict[UUID, GeoPoint],
    *,
    now: datetime,
    travel: TravelTimeProvider | None = None,
    trip_type: str | None = None,
) -> DetourResult:
    """
    Evaluate inserting guest pickup/drop into an in-progress trip.
    Uses live_position as route start — not trip origin.
    Excludes at_pickup (caller should also filter).
    """
    travel = travel or CachedTravelProvider()
    trip = driver.current_trip
    if trip is None:
        return DetourResult(False, reason="no_active_trip")
    if trip.locked_by_override:
        return DetourResult(False, reason="override_locked")
    if driver.status == "at_pickup":
        return DetourResult(False, reason="at_pickup_excluded")
    if driver.status not in {"en_route", "in_trip"}:
        return DetourResult(False, reason="status_not_eligible")
    if driver.live_position is None:
        return DetourResult(False, reason="no_live_position")
    if not can_accept(driver, guest.party_size, guest.luggage_count):
        return DetourResult(False, reason="capacity")

    remaining = [s for s in trip.stops if not s.completed]
    if not remaining:
        return DetourResult(False, reason="no_remaining_stops")

    pickup = locations[guest.pickup_location_id]
    drop = locations[guest.drop_location_id]
    new_pickup = StopSnapshot(
        location_id=guest.pickup_location_id,
        lat=pickup.lat,
        lng=pickup.lng,
        stop_type="pickup",
        guest_id=guest.guest_id,
        sequence=-1,
        deadline_at=guest.deadline_at,
    )
    new_drop = StopSnapshot(
        location_id=guest.drop_location_id,
        lat=drop.lat,
        lng=drop.lng,
        stop_type="drop",
        guest_id=guest.guest_id,
        sequence=-1,
        deadline_at=guest.deadline_at,
    )

    baseline_points = [driver.live_position] + [GeoPoint(s.lat, s.lng) for s in remaining]
    baseline_secs = travel.path_duration(baseline_points, now=now)

    best: DetourResult | None = None

    # Insert pickup at i, drop at j > i
    n = len(remaining)
    for i in range(n + 1):
        for j in range(i + 1, n + 2):
            candidate = remaining[:i] + [new_pickup] + remaining[i : j - 1] + [new_drop] + remaining[j - 1 :]
            # Validate pickup before drop for new guest — guaranteed by construction
            points = [driver.live_position] + [GeoPoint(s.lat, s.lng) for s in candidate]
            total_secs = travel.path_duration(points, now=now)
            added_min = (total_secs - baseline_secs) / 60.0
            if added_min > MAX_DETOUR_INSERTION_MINUTES + 1e-6:
                continue

            etas = _etas_along(points, now, travel)
            # Map stop -> eta (skip index 0 = live position)
            ok = True
            drop_eta_new: datetime | None = None
            for idx, stop in enumerate(candidate):
                eta = etas[idx + 1]
                if stop.deadline_at and eta > stop.deadline_at:
                    ok = False
                    break
                if stop.guest_id == guest.guest_id and stop.stop_type == "drop":
                    drop_eta_new = eta
            if not ok:
                continue
            if guest.deadline_at and drop_eta_new and drop_eta_new > guest.deadline_at:
                continue

            proposed_stops = tuple(
                ProposedStop(
                    location_id=s.location_id,
                    stop_type=s.stop_type,
                    guest_id=s.guest_id,
                    sequence=seq,
                    deadline_at=s.deadline_at,
                    eta_at=etas[seq + 1],
                )
                for seq, s in enumerate(candidate)
            )
            pickup_eta = next(s.eta_at for s in proposed_stops if s.guest_id == guest.guest_id and s.stop_type == "pickup")
            result = DetourResult(
                accepted=True,
                added_minutes=added_min,
                reason="ok",
                trip=ProposedTrip(
                    driver_id=driver.driver_id,
                    vehicle_id=driver.vehicle_id,
                    guest_ids=_merge_guest_ids(trip, guest.guest_id),
                    origin_location_id=remaining[0].location_id,
                    dest_location_id=guest.drop_location_id,
                    trip_type=trip_type or trip.trip_type,
                    seats_used=trip.seats_used + guest.party_size,
                    luggage_used=trip.luggage_used + guest.luggage_count,
                    scheduled_pickup_at=guest.ready_at,
                    eta_pickup=pickup_eta,
                    eta_drop=drop_eta_new,
                    stops=proposed_stops,
                    source="detour",
                    existing_trip_id=trip.trip_id,
                    expected_route_version=trip.route_version,
                    notes=f"detour_added_min={added_min:.2f}",
                ),
            )
            if best is None or result.added_minutes < best.added_minutes:
                best = result

    return best or DetourResult(False, reason="no_feasible_insert")


def _etas_along(points: list[GeoPoint], now: datetime, travel: TravelTimeProvider) -> list[datetime]:
    etas = [now]
    for a, b in zip(points[:-1], points[1:]):
        secs = travel.duration_seconds(a, b, now=now)
        etas.append(etas[-1] + timedelta(seconds=secs))
    return etas


def _merge_guest_ids(trip, new_guest_id: UUID) -> tuple[UUID, ...]:
    existing = []
    for s in trip.stops:
        if s.guest_id and s.guest_id not in existing:
            existing.append(s.guest_id)
    if new_guest_id not in existing:
        existing.append(new_guest_id)
    return tuple(existing)
