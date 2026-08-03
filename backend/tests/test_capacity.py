from datetime import timedelta

from app.matching_engine.capacity import (
    fleet_can_cover,
    needs_split,
    prepare_guests_for_matching,
    split_party,
)
from app.matching_engine.types import UnmatchedReason
from tests.conftest import make_driver, make_guest


def test_fits_single_vehicle(locs, now):
    drivers = [make_driver(seats=4, luggage=3)]
    guest = make_guest(locs, party=2, luggage=2, now=now)
    assert not needs_split(guest, drivers)


def test_split_group_exceeds_largest_vehicle(locs, now):
    drivers = [make_driver(seats=4, luggage=3), make_driver(seats=6, luggage=4)]
    guest = make_guest(locs, party=10, luggage=8, now=now)
    assert needs_split(guest, drivers)
    splits, err = split_party(guest, drivers)
    assert err is None
    assert len(splits) >= 2
    assert sum(s.party_size for s in splits) == 10
    assert all(s.party_group_id == splits[0].party_group_id for s in splits)


def test_fleet_escalation_when_capacity_insufficient(locs, now):
    drivers = [make_driver(seats=4, luggage=2)]
    guest = make_guest(locs, party=20, luggage=20, now=now)
    matchable, unmatched, _ = prepare_guests_for_matching([guest], drivers)
    assert matchable == []
    assert unmatched[0].reason == UnmatchedReason.needs_escalation


def test_fleet_can_cover_true(locs, now):
    drivers = [make_driver(seats=7, luggage=5), make_driver(seats=7, luggage=5)]
    guest = make_guest(locs, party=10, luggage=8, now=now)
    splits, _ = split_party(guest, drivers)
    assert fleet_can_cover(splits, drivers)
