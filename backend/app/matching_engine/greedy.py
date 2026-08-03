"""Lightweight greedy matcher for one-off / approved on-demand requests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.constants import MANDATORY_BREAK_MINUTES
from app.matching_engine.capacity import can_accept, fits_vehicle, needs_split, prepare_guests_for_matching
from app.matching_engine.detour import try_detour
from app.matching_engine.routing import CachedTravelProvider, TravelTimeProvider
from app.matching_engine.types import (
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    MatchOneResult,
    ProposedStop,
    ProposedTrip,
    UnmatchedGuest,
    UnmatchedReason,
)


DETOUR_ELIGIBLE = frozenset({"en_route", "in_trip"})
AVAILABLE = frozenset({"available"})


def _driver_assignable(driver: DriverSnapshot, now: datetime) -> bool:
    if driver.status == "offline":
        return False
    if driver.status == "on_break":
        return False
    if driver.break_until is not None and driver.break_until > now:
        return False
    if driver.cool_down_until is not None and driver.cool_down_until > now:
        return False
    if driver.current_trip and driver.current_trip.locked_by_override:
        return False
    return True


def _start_point(driver: DriverSnapshot, now: datetime) -> tuple[GeoPoint, datetime]:
    """Where/when the driver can begin serving a new pickup."""
    if driver.status in AVAILABLE and driver.live_position:
        return driver.live_position, now
    if driver.predicted_free_at and driver.predicted_free_position:
        free_at = driver.predicted_free_at + timedelta(minutes=MANDATORY_BREAK_MINUTES)
        return driver.predicted_free_position, max(now, free_at)
    if driver.live_position:
        return driver.live_position, now
    return driver.depot, now


def match_one(
    guest: GuestSnapshot,
    drivers: list[DriverSnapshot],
    locations: dict,  # UUID -> GeoPoint
    *,
    now: datetime,
    travel: TravelTimeProvider | None = None,
    trip_type: str = "arrival",
) -> MatchOneResult:
    """
    Pure greedy match. Does not mutate inputs or touch IO beyond travel provider.
    Tries available drivers first; then detour-eligible mid-trip drivers.
    """
    travel = travel or CachedTravelProvider()

    if needs_split(guest, drivers):
        matchable, unmatched, _ = prepare_guests_for_matching([guest], drivers)
        if unmatched:
            return MatchOneResult(matched=False, unmatched=unmatched[0])
        trips: list[ProposedTrip] = []
        working = list(drivers)
        for part in matchable:
            # Force non-split path for each chunk
            res = _match_single(part, working, locations, now=now, travel=travel, trip_type=trip_type)
            if not res.matched or not res.trip:
                return MatchOneResult(
                    matched=False,
                    unmatched=UnmatchedGuest(
                        guest.guest_id,
                        UnmatchedReason.needs_escalation,
                        "could not assign all split parts",
                    ),
                )
            trips.append(res.trip)
            # One split chunk per vehicle — remove assigned driver from pool
            working = [d for d in working if d.driver_id != res.trip.driver_id]
        return MatchOneResult(matched=True, trip=trips[0], trips=tuple(trips))

    return _match_single(guest, drivers, locations, now=now, travel=travel, trip_type=trip_type)


def _match_single(
    guest: GuestSnapshot,
    drivers: list[DriverSnapshot],
    locations: dict,
    *,
    now: datetime,
    travel: TravelTimeProvider,
    trip_type: str,
) -> MatchOneResult:
    pickup = locations[guest.pickup_location_id]
    drop = locations[guest.drop_location_id]
    best: MatchOneResult | None = None
    best_score = float("inf")

    for driver in drivers:
        if not _driver_assignable(driver, now):
            if driver.status == "offline":
                continue
            continue

        if driver.status == "at_pickup":
            continue  # never detour / assign new work during pickup handshake

        if driver.status in AVAILABLE:
            if not fits_vehicle(guest, driver.seat_capacity, driver.luggage_capacity):
                continue
            if not can_accept(driver, guest.party_size, guest.luggage_count):
                continue
            start, start_time = _start_point(driver, now)
            to_pickup = travel.duration_seconds(start, pickup, now=now)
            pickup_eta = max(start_time, guest.ready_at) + timedelta(seconds=to_pickup)
            # If driver arrives before guest ready, wait
            if start_time + timedelta(seconds=to_pickup) < guest.ready_at:
                pickup_eta = guest.ready_at
            trip_secs = travel.duration_seconds(pickup, drop, now=now)
            drop_eta = pickup_eta + timedelta(seconds=trip_secs)

            if guest.deadline_at and drop_eta > guest.deadline_at:
                continue

            wait_for_guest = max(0.0, (pickup_eta - guest.ready_at).total_seconds())
            score = wait_for_guest + to_pickup
            if guest.priority:
                score -= 120  # soft preference
            if score < best_score:
                best_score = score
                best = MatchOneResult(
                    matched=True,
                    trip=ProposedTrip(
                        driver_id=driver.driver_id,
                        vehicle_id=driver.vehicle_id,
                        guest_ids=(guest.guest_id,),
                        origin_location_id=guest.pickup_location_id,
                        dest_location_id=guest.drop_location_id,
                        trip_type=trip_type,
                        seats_used=guest.party_size,
                        luggage_used=guest.luggage_count,
                        scheduled_pickup_at=guest.ready_at,
                        eta_pickup=pickup_eta,
                        eta_drop=drop_eta,
                        stops=(
                            ProposedStop(
                                guest.pickup_location_id, "pickup", guest.guest_id, 0, guest.deadline_at, pickup_eta
                            ),
                            ProposedStop(
                                guest.drop_location_id, "drop", guest.guest_id, 1, guest.deadline_at, drop_eta
                            ),
                        ),
                        party_group_id=guest.party_group_id,
                        source="greedy",
                    ),
                )
            continue

        if driver.status in DETOUR_ELIGIBLE and driver.current_trip:
            detour = try_detour(driver, guest, locations, now=now, travel=travel, trip_type=trip_type)
            if not detour.accepted or not detour.trip:
                continue
            score = detour.added_minutes * 60
            if score < best_score:
                best_score = score
                best = MatchOneResult(matched=True, trip=detour.trip, is_detour=True)

    if best is not None:
        return best

    # Distinguish offline-only fleet vs capacity
    if drivers and all(d.status == "offline" for d in drivers):
        return MatchOneResult(
            matched=False,
            unmatched=UnmatchedGuest(guest.guest_id, UnmatchedReason.driver_offline, "all drivers offline"),
        )
    return MatchOneResult(
        matched=False,
        unmatched=UnmatchedGuest(guest.guest_id, UnmatchedReason.no_feasible_driver, "no feasible driver"),
    )
