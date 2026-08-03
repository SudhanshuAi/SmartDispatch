from datetime import timedelta

from app.matching_engine.batch import run_batch
from app.matching_engine.types import UnmatchedReason
from tests.conftest import make_driver, make_guest


def test_batch_assigns_known_arrivals(locs, now, travel):
    drivers = [make_driver(seats=4), make_driver(seats=6), make_driver(seats=7)]
    guests = [make_guest(locs, now=now, ready_offset_min=i * 10, deadline_offset_min=180) for i in range(8)]
    result = run_batch(guests, drivers, locs["map"], now=now, travel=travel)
    assigned = sum(len(t.guest_ids) for t in result.trips)
    assert assigned >= 1
    assert all(t.source == "batch" for t in result.trips)


def test_batch_respects_capacity(locs, now, travel):
    drivers = [make_driver(seats=2, luggage=1)]
    guests = [
        make_guest(locs, party=2, luggage=1, now=now, deadline_offset_min=180),
        make_guest(locs, party=2, luggage=1, now=now, ready_offset_min=5, deadline_offset_min=180),
    ]
    result = run_batch(guests, drivers, locs["map"], now=now, travel=travel)
    # Only one party of 2 fits
    total_seats = sum(t.seats_used for t in result.trips)
    assert total_seats <= 2
    assert len(result.unmatched) >= 1


def test_batch_escalates_huge_party(locs, now, travel):
    drivers = [make_driver(seats=4)]
    guests = [make_guest(locs, party=50, luggage=40, now=now)]
    result = run_batch(guests, drivers, locs["map"], now=now, travel=travel)
    assert any(u.reason == UnmatchedReason.needs_escalation for u in result.unmatched)
