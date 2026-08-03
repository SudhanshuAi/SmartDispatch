"""Travel-time provider with in-memory distance cache (no Maps hammering)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.matching_engine.types import GeoPoint


def haversine_meters(a: GeoPoint, b: GeoPoint) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlambda = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_seconds(a: GeoPoint, b: GeoPoint, *, speed_mps: float = 8.33) -> int:
    """~30 km/h urban default when Maps is unavailable / mocked."""
    meters = haversine_meters(a, b)
    return max(60, int(meters / speed_mps))


def od_cache_key(a: GeoPoint, b: GeoPoint, bucket_minutes: int = 5) -> str:
    # Round coords to ~11m to stabilize keys
    return f"{a.lat:.4f},{a.lng:.4f}->{b.lat:.4f},{b.lng:.4f}@{bucket_minutes}"


@dataclass
class CacheEntry:
    duration_seconds: int
    distance_meters: int
    expires_at: datetime


class TravelTimeProvider(Protocol):
    def duration_seconds(self, origin: GeoPoint, dest: GeoPoint, *, now: datetime) -> int: ...

    def batch_durations(
        self, pairs: list[tuple[GeoPoint, GeoPoint]], *, now: datetime
    ) -> list[int]: ...

    @property
    def matrix_calls(self) -> int: ...

    @property
    def cache_hits(self) -> int: ...


@dataclass
class CachedTravelProvider:
    """
    Batches OD lookups and caches results.
    Optional `fetcher` simulates Distance Matrix; default uses haversine estimate.
    """

    ttl: timedelta = timedelta(minutes=3)
    planning_ttl: timedelta = timedelta(minutes=30)
    traffic_mode: bool = True
    fetcher: object | None = None
    _cache: dict[str, CacheEntry] = field(default_factory=dict)
    _matrix_calls: int = 0
    _cache_hits: int = 0

    @property
    def matrix_calls(self) -> int:
        return self._matrix_calls

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    def _ttl(self) -> timedelta:
        return self.ttl if self.traffic_mode else self.planning_ttl

    def _fetch_one(self, origin: GeoPoint, dest: GeoPoint) -> tuple[int, int]:
        if self.fetcher is not None:
            return self.fetcher(origin, dest)
        meters = int(haversine_meters(origin, dest))
        return estimate_seconds(origin, dest), meters

    def duration_seconds(self, origin: GeoPoint, dest: GeoPoint, *, now: datetime) -> int:
        return self.batch_durations([(origin, dest)], now=now)[0]

    def batch_durations(
        self, pairs: list[tuple[GeoPoint, GeoPoint]], *, now: datetime
    ) -> list[int]:
        results: list[int | None] = [None] * len(pairs)
        miss_indices: list[int] = []
        for i, (o, d) in enumerate(pairs):
            key = od_cache_key(o, d)
            entry = self._cache.get(key)
            if entry is not None and entry.expires_at > now:
                results[i] = entry.duration_seconds
                self._cache_hits += 1
            else:
                miss_indices.append(i)

        if miss_indices:
            # One logical matrix round-trip for all misses
            self._matrix_calls += 1
            expires = now + self._ttl()
            for i in miss_indices:
                o, d = pairs[i]
                dur, dist = self._fetch_one(o, d)
                self._cache[od_cache_key(o, d)] = CacheEntry(dur, dist, expires)
                results[i] = dur

        return [int(r) for r in results]  # type: ignore[arg-type]

    def path_duration(
        self, points: list[GeoPoint], *, now: datetime
    ) -> int:
        if len(points) < 2:
            return 0
        pairs = list(zip(points[:-1], points[1:]))
        return sum(self.batch_durations(pairs, now=now))


def location_map(locations: dict[UUID, GeoPoint]) -> dict[UUID, GeoPoint]:
    return locations
