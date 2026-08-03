"""
Matching engine package — pure decisioning (no HTTP / SQLAlchemy).

Use DispatchMatchingEngine or the functional APIs (match_one, run_batch, try_detour, plan_reopt).
"""

from app.matching_engine.engine import DispatchMatchingEngine
from app.matching_engine.priority_queue import InMemoryPriorityQueue, priority_score
from app.matching_engine.routing import CachedTravelProvider
from app.matching_engine.versioning import apply_version_guard, next_route_version

__all__ = [
    "DispatchMatchingEngine",
    "InMemoryPriorityQueue",
    "priority_score",
    "CachedTravelProvider",
    "apply_version_guard",
    "next_route_version",
]
