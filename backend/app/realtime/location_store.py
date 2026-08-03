"""Hot driver location in Redis + dirty-trip flags for reopt."""

from __future__ import annotations

import json
import time
from uuid import UUID

from app.redis_client import get_redis

LOC_KEY = "smartdispatch:driver:loc:{driver_id}"
DIRTY_SET = "smartdispatch:trips:dirty"
REOPT_LAST_RUN = "smartdispatch:reopt:last_run"
PUSH_TOKEN_KEY = "smartdispatch:push:{role}:{subject_id}"


def set_driver_location(
    driver_id: UUID,
    *,
    lat: float,
    lng: float,
    heading: float | None = None,
    speed: float | None = None,
    trip_id: UUID | None = None,
) -> dict:
    payload = {
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "speed": speed,
        "trip_id": str(trip_id) if trip_id else None,
        "ts": time.time(),
    }
    r = get_redis()
    if r is not None:
        r.set(LOC_KEY.format(driver_id=driver_id), json.dumps(payload), ex=3600)
        if trip_id:
            r.sadd(DIRTY_SET, str(trip_id))
    return payload


def get_driver_location(driver_id: UUID) -> dict | None:
    r = get_redis()
    if r is None:
        return None
    raw = r.get(LOC_KEY.format(driver_id=driver_id))
    if not raw:
        return None
    return json.loads(raw)


def mark_trip_dirty(trip_id: UUID) -> None:
    r = get_redis()
    if r is not None:
        r.sadd(DIRTY_SET, str(trip_id))


def pop_dirty_trips() -> list[UUID]:
    r = get_redis()
    if r is None:
        return []
    ids = list(r.smembers(DIRTY_SET) or [])
    if ids:
        r.delete(DIRTY_SET)
    return [UUID(x) for x in ids]


def get_last_reopt_ts() -> float | None:
    r = get_redis()
    if r is None:
        return None
    v = r.get(REOPT_LAST_RUN)
    return float(v) if v else None


def set_last_reopt_ts(ts: float | None = None) -> None:
    r = get_redis()
    if r is not None:
        r.set(REOPT_LAST_RUN, str(ts if ts is not None else time.time()))


def set_push_token(role: str, subject_id: UUID, token: str) -> None:
    r = get_redis()
    if r is not None:
        r.set(PUSH_TOKEN_KEY.format(role=role, subject_id=subject_id), token, ex=60 * 60 * 24 * 30)


def get_push_token(role: str, subject_id: UUID) -> str | None:
    r = get_redis()
    if r is None:
        return None
    return r.get(PUSH_TOKEN_KEY.format(role=role, subject_id=subject_id))
