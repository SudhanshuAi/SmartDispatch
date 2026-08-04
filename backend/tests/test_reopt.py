from datetime import timedelta
from uuid import uuid4

from app.matching_engine.reopt import plan_reopt
from app.matching_engine.routing import CachedTravelProvider
from app.matching_engine.types import GeoPoint, ReoptTripInput, StopSnapshot


def _trip(now, *, drift_eta_minutes=0, dirty=True, deadline_minutes=120):
    airport = GeoPoint(28.5562, 77.1000)
    hotel = GeoPoint(28.6205, 77.2150)
    gid = uuid4()
    return ReoptTripInput(
        trip_id=uuid4(),
        driver_id=uuid4(),
        route_version=1,
        needs_eta_refresh=dirty,
        current_eta_drop=now + timedelta(minutes=30 + drift_eta_minutes),
        guest_deadlines=(now + timedelta(minutes=deadline_minutes),),
        boarded_guest_ids=(),
        stops=(
            StopSnapshot(uuid4(), airport.lat, airport.lng, "pickup", gid, 0, now + timedelta(minutes=deadline_minutes)),
            StopSnapshot(uuid4(), hotel.lat, hotel.lng, "drop", gid, 1, now + timedelta(minutes=deadline_minutes)),
        ),
        live_position=GeoPoint(28.56, 77.11),
        seats_used=1,
        luggage_used=1,
    )


def test_reopt_debounces_frequent_ticks(now):
    travel = CachedTravelProvider()
    trips = [_trip(now) for _ in range(3)]
    first = plan_reopt(trips, now=now, travel=travel, last_run_at=None)
    assert len(first.actions) == 3
    # Immediate second run within debounce with few dirty — skipped
    second = plan_reopt(trips, now=now + timedelta(seconds=5), travel=travel, last_run_at=now)
    assert second.actions == ()


def test_reopt_batches_matrix_calls(now):
    travel = CachedTravelProvider()
    trips = [_trip(now) for _ in range(10)]
    result = plan_reopt(trips, now=now, travel=travel, last_run_at=None)
    # One matrix round-trip for all misses, not 10
    assert result.matrix_calls == 1
    assert len(result.actions) == 10


def test_reopt_cache_hits_on_second_pass(now):
    travel = CachedTravelProvider()
    trips = [_trip(now) for _ in range(5)]
    plan_reopt(trips, now=now, travel=travel, last_run_at=None)
    # Force flush by dirty count / time
    later = now + timedelta(seconds=60)
    result = plan_reopt(trips, now=later, travel=travel, last_run_at=now)
    assert result.cache_hits >= 1


def test_reopt_rematch_on_deadline_risk(now):
    travel = CachedTravelProvider()
    # Very short deadline so path will breach
    t = _trip(now, deadline_minutes=1)
    result = plan_reopt([t], now=now, travel=travel, last_run_at=None)
    assert result.actions[0].action in {"rematch", "refresh_eta"}


def test_driver_offline_mid_trip_not_in_engine_scope_but_reopt_still_refreshes(now):
    """Reopt refreshes ETAs for in-progress trips even if driver later marked offline elsewhere."""
    travel = CachedTravelProvider()
    t = _trip(now)
    result = plan_reopt([t], now=now, travel=travel)
    assert result.actions[0].trip_id == t.trip_id


def test_reopt_pickup_eta_respects_ready_floor(now):
    """Live travel shorter than plan must not pull pickup ETA before ready_at."""
    travel = CachedTravelProvider()
    airport = GeoPoint(28.5562, 77.1000)
    hotel = GeoPoint(28.6205, 77.2150)
    gid = uuid4()
    ready = now + timedelta(hours=3)
    t = ReoptTripInput(
        trip_id=uuid4(),
        driver_id=uuid4(),
        route_version=1,
        needs_eta_refresh=True,
        current_eta_drop=ready + timedelta(minutes=40),
        current_eta_pickup=ready,
        pickup_ready_at=ready,
        guest_deadlines=(ready + timedelta(hours=2),),
        boarded_guest_ids=(),
        stops=(
            StopSnapshot(uuid4(), airport.lat, airport.lng, "pickup", gid, 0, ready + timedelta(hours=2)),
            StopSnapshot(uuid4(), hotel.lat, hotel.lng, "drop", gid, 1, ready + timedelta(hours=2)),
        ),
        live_position=GeoPoint(28.56, 77.11),
        seats_used=1,
        luggage_used=1,
    )
    result = plan_reopt([t], now=now, travel=travel, last_run_at=None)
    assert result.actions[0].action == "refresh_eta"
    assert result.actions[0].new_eta_pickup is not None
    assert result.actions[0].new_eta_pickup >= ready
    assert result.actions[0].new_eta_drop is not None
    assert result.actions[0].new_eta_drop > result.actions[0].new_eta_pickup


def test_reopt_skips_pickup_eta_after_pickup_completed(now):
    travel = CachedTravelProvider()
    airport = GeoPoint(28.5562, 77.1000)
    hotel = GeoPoint(28.6205, 77.2150)
    gid = uuid4()
    t = ReoptTripInput(
        trip_id=uuid4(),
        driver_id=uuid4(),
        route_version=1,
        needs_eta_refresh=True,
        current_eta_drop=now + timedelta(minutes=30),
        current_eta_pickup=now - timedelta(minutes=5),
        pickup_ready_at=now - timedelta(hours=1),
        guest_deadlines=(now + timedelta(hours=2),),
        boarded_guest_ids=(),
        stops=(
            StopSnapshot(
                uuid4(), airport.lat, airport.lng, "pickup", gid, 0, None, completed=True
            ),
            StopSnapshot(uuid4(), hotel.lat, hotel.lng, "drop", gid, 1, now + timedelta(hours=2)),
        ),
        live_position=airport,
        seats_used=1,
        luggage_used=1,
    )
    result = plan_reopt([t], now=now, travel=travel, last_run_at=None)
    assert result.actions[0].new_eta_pickup is None
    assert result.actions[0].new_eta_drop is not None
