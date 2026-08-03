from datetime import timedelta
from uuid import uuid4

from app.constants import MATCH_ONE_P95_MS
from app.matching_engine.greedy import match_one
from app.matching_engine.types import UnmatchedReason
from tests.conftest import active_trip, make_driver, make_guest


def test_match_one_assigns_available_driver(locs, now, travel):
    drivers = [make_driver(seats=4), make_driver(seats=6)]
    guest = make_guest(locs, now=now)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert res.matched
    assert res.trip is not None
    assert res.trip.driver_id in {d.driver_id for d in drivers}


def test_no_feasible_driver(locs, now, travel):
    drivers = [make_driver(status="on_break", break_until=now + timedelta(hours=1))]
    guest = make_guest(locs, now=now)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert not res.matched
    assert res.unmatched is not None
    assert res.unmatched.reason == UnmatchedReason.no_feasible_driver


def test_all_drivers_offline(locs, now, travel):
    drivers = [make_driver(status="offline"), make_driver(status="offline")]
    guest = make_guest(locs, now=now)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert not res.matched
    assert res.unmatched.reason == UnmatchedReason.driver_offline


def test_deadline_about_to_be_missed(locs, now, travel):
    # Driver far away, deadline very tight
    drivers = [make_driver(lat=28.0, lng=76.0)]  # far from airport
    guest = make_guest(locs, now=now, deadline_offset_min=5)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert not res.matched


def test_group_too_large_escalates(locs, now, travel):
    drivers = [make_driver(seats=4, luggage=2)]
    guest = make_guest(locs, party=30, luggage=30, now=now)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert not res.matched
    assert res.unmatched.reason == UnmatchedReason.needs_escalation


def test_split_assigns_multiple_trips(locs, now, travel):
    drivers = [make_driver(seats=4, luggage=3), make_driver(seats=4, luggage=3), make_driver(seats=4, luggage=3)]
    guest = make_guest(locs, party=10, luggage=6, now=now, deadline_offset_min=180)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert res.matched
    assert len(res.all_trips()) >= 2


def test_match_one_p95_under_500ms(locs, now, travel):
    import time

    drivers = [make_driver(seats=4 if i % 2 == 0 else 7, luggage=3 + (i % 3)) for i in range(100)]
    samples = []
    for i in range(40):
        guest = make_guest(locs, now=now, ready_offset_min=i)
        t0 = time.perf_counter()
        match_one(guest, drivers, locs["map"], now=now, travel=travel)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p95 = samples[int(0.95 * (len(samples) - 1))]
    assert p95 <= MATCH_ONE_P95_MS, f"p95={p95:.1f}ms exceeds {MATCH_ONE_P95_MS}ms"


def test_at_pickup_not_used_for_new_match(locs, now, travel):
    g0 = uuid4()
    trip = active_trip(locs, g0, deadline=now + timedelta(hours=2))
    drivers = [make_driver(status="at_pickup", trip=trip, seats=6, luggage=5)]
    guest = make_guest(locs, now=now)
    res = match_one(guest, drivers, locs["map"], now=now, travel=travel)
    assert not res.matched
