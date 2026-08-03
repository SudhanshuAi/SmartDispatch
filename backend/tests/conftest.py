"""Shared fixtures for matching-engine unit tests (no DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.matching_engine.routing import CachedTravelProvider
from app.matching_engine.types import (
    ActiveTripSnapshot,
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    StopSnapshot,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def travel() -> CachedTravelProvider:
    return CachedTravelProvider(traffic_mode=True)


@pytest.fixture
def locs():
    airport = uuid4()
    hotel_a = uuid4()
    hotel_b = uuid4()
    station = uuid4()
    return {
        "airport_id": airport,
        "hotel_a_id": hotel_a,
        "hotel_b_id": hotel_b,
        "station_id": station,
        "map": {
            airport: GeoPoint(28.5562, 77.1000),
            hotel_a: GeoPoint(28.6205, 77.2150),
            hotel_b: GeoPoint(28.6080, 77.2250),
            station: GeoPoint(28.6430, 77.2190),
        },
    }


def make_driver(
    *,
    seats: int = 4,
    luggage: int = 3,
    status: str = "available",
    lat: float = 28.6139,
    lng: float = 77.2090,
    trip: ActiveTripSnapshot | None = None,
    break_until: datetime | None = None,
) -> DriverSnapshot:
    return DriverSnapshot(
        driver_id=uuid4(),
        vehicle_id=uuid4(),
        seat_capacity=seats,
        luggage_capacity=luggage,
        status=status,
        break_until=break_until,
        live_position=GeoPoint(lat, lng),
        predicted_free_at=None,
        predicted_free_position=None,
        depot=GeoPoint(lat, lng),
        current_trip=trip,
    )


def make_guest(
    locs,
    *,
    party: int = 1,
    luggage: int = 1,
    pickup: str = "airport_id",
    drop: str = "hotel_a_id",
    ready_offset_min: int = 0,
    deadline_offset_min: int = 60,
    priority: bool = False,
    now: datetime | None = None,
) -> GuestSnapshot:
    base = now or datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)
    return GuestSnapshot(
        guest_id=uuid4(),
        party_size=party,
        luggage_count=luggage,
        pickup_location_id=locs[pickup],
        drop_location_id=locs[drop],
        ready_at=base + timedelta(minutes=ready_offset_min),
        deadline_at=base + timedelta(minutes=deadline_offset_min),
        priority=priority,
    )


def active_trip(
    locs,
    guest_id,
    *,
    seats_used: int = 1,
    luggage_used: int = 1,
    route_version: int = 1,
    pickup_key: str = "airport_id",
    drop_key: str = "hotel_a_id",
    deadline: datetime | None = None,
) -> ActiveTripSnapshot:
    p, d = locs[pickup_key], locs[drop_key]
    pm, dm = locs["map"][p], locs["map"][d]
    return ActiveTripSnapshot(
        trip_id=uuid4(),
        route_version=route_version,
        seats_used=seats_used,
        luggage_used=luggage_used,
        trip_type="arrival",
        stops=(
            StopSnapshot(p, pm.lat, pm.lng, "pickup", guest_id, 0, deadline),
            StopSnapshot(d, dm.lat, dm.lng, "drop", guest_id, 1, deadline),
        ),
    )
