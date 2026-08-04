"""Re-export facade (engine.py name used in __init__)."""

from app.matching_engine.batch import run_batch
from app.matching_engine.detour import try_detour
from app.matching_engine.greedy import match_one
from app.matching_engine.reopt import plan_reopt
from app.matching_engine.routing import CachedTravelProvider

__all__ = ["DispatchMatchingEngine", "match_one", "run_batch", "try_detour", "plan_reopt"]


class DispatchMatchingEngine:
    def __init__(self, travel=None) -> None:  # noqa: ANN001
        self.travel = travel or CachedTravelProvider()

    def match_one(self, guest, drivers, locations, *, now, trip_type="arrival"):  # noqa: ANN001
        return match_one(guest, drivers, locations, now=now, travel=self.travel, trip_type=trip_type)

    def run_batch(self, guests, drivers, locations, *, now, trip_type="arrival", **kwargs):  # noqa: ANN001
        return run_batch(
            guests, drivers, locations, now=now, travel=self.travel, trip_type=trip_type, **kwargs
        )

    def try_detour(self, driver, guest, locations, *, now):  # noqa: ANN001
        return try_detour(driver, guest, locations, now=now, travel=self.travel)

    def plan_reopt(self, trips, *, now, last_run_at=None):  # noqa: ANN001
        return plan_reopt(trips, now=now, travel=self.travel, last_run_at=last_run_at)
