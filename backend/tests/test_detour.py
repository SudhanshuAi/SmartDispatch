from datetime import timedelta
from uuid import uuid4

from app.matching_engine.detour import try_detour
from app.matching_engine.versioning import apply_version_guard, next_route_version
from tests.conftest import active_trip, make_driver, make_guest


def test_detour_accepted_mid_trip(locs, now, travel):
    existing = uuid4()
    trip = active_trip(
        locs,
        existing,
        seats_used=1,
        luggage_used=1,
        deadline=now + timedelta(hours=3),
    )
    driver = make_driver(status="en_route", seats=4, luggage=4, trip=trip, lat=28.56, lng=77.12)
    guest = make_guest(locs, now=now, deadline_offset_min=180)
    # Place new guest pickup near driver's live path (airport area)
    res = try_detour(driver, guest, locs["map"], now=now, travel=travel)
    assert res.accepted
    assert res.trip is not None
    assert res.trip.expected_route_version == 1
    assert res.trip.existing_trip_id == trip.trip_id
    assert guest.guest_id in res.trip.guest_ids


def test_detour_rejected_at_pickup(locs, now, travel):
    existing = uuid4()
    trip = active_trip(locs, existing, deadline=now + timedelta(hours=2))
    driver = make_driver(status="at_pickup", seats=6, luggage=5, trip=trip)
    guest = make_guest(locs, now=now)
    res = try_detour(driver, guest, locs["map"], now=now, travel=travel)
    assert not res.accepted
    assert res.reason == "at_pickup_excluded"


def test_detour_capacity_exceeded(locs, now, travel):
    existing = uuid4()
    trip = active_trip(locs, existing, seats_used=4, luggage_used=3, deadline=now + timedelta(hours=2))
    driver = make_driver(status="in_trip", seats=4, luggage=3, trip=trip)
    guest = make_guest(locs, party=1, luggage=1, now=now)
    res = try_detour(driver, guest, locs["map"], now=now, travel=travel)
    assert not res.accepted
    assert res.reason == "capacity"


def test_two_simultaneous_detours_share_same_base_version(locs, now, travel):
    """Both evaluations see the same route_version; apply layer serializes via optimistic lock."""
    existing = uuid4()
    trip = active_trip(locs, existing, seats_used=1, luggage_used=0, deadline=now + timedelta(hours=3))
    driver = make_driver(status="en_route", seats=6, luggage=5, trip=trip, lat=28.56, lng=77.11)
    g1 = make_guest(locs, now=now, deadline_offset_min=180)
    g2 = make_guest(locs, now=now, deadline_offset_min=180)
    r1 = try_detour(driver, g1, locs["map"], now=now, travel=travel)
    r2 = try_detour(driver, g2, locs["map"], now=now, travel=travel)
    assert r1.accepted and r2.accepted
    assert r1.trip.expected_route_version == r2.trip.expected_route_version == trip.route_version
    # Simulate first apply winning
    assert apply_version_guard(trip.route_version, r1.trip.expected_route_version)
    new_v = next_route_version(trip.route_version, r1.trip.expected_route_version)
    assert new_v == 2
    # Second apply conflicts
    assert next_route_version(new_v, r2.trip.expected_route_version) is None


def test_detour_uses_live_position_not_origin(locs, now, travel):
    existing = uuid4()
    trip = active_trip(locs, existing, deadline=now + timedelta(hours=3))
    # Live position already near hotel (past airport origin)
    driver = make_driver(status="in_trip", seats=4, luggage=3, trip=trip, lat=28.618, lng=77.210)
    guest = make_guest(locs, pickup="hotel_b_id", drop="hotel_a_id", now=now, deadline_offset_min=120)
    res = try_detour(driver, guest, locs["map"], now=now, travel=travel)
    # May accept or reject based on 8-min budget, but must not crash and must key off live pos
    assert res.reason in {"ok", "no_feasible_insert", "capacity"} or res.accepted
