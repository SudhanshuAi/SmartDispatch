"""Re-optimization triggers with debounce, selective rematch, batched travel lookups."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.matching_engine.routing import CachedTravelProvider, TravelTimeProvider
from app.matching_engine.types import GeoPoint, ReoptAction, ReoptResult, ReoptTripInput

DEFAULT_DEBOUNCE_SECONDS = 45
ETA_DRIFT_THRESHOLD_MINUTES = 4.0
DIRTY_COUNT_FLUSH = 8


def plan_reopt(
    trips: list[ReoptTripInput],
    *,
    now: datetime,
    travel: TravelTimeProvider | None = None,
    last_run_at: datetime | None = None,
    debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS,
    drift_threshold_minutes: float = ETA_DRIFT_THRESHOLD_MINUTES,
) -> ReoptResult:
    """
    Decide ETA refresh vs rematch for dirty / drifted trips.
    Does not call Maps per GPS tick — batches OD pairs and respects debounce.

    Pickup ETA is only refreshed while pickup stops remain incomplete, and never
    earlier than pickup_ready_at / current_eta_pickup (scheduled plan floor).
    """
    travel = travel or CachedTravelProvider(traffic_mode=True)

    dirty = [t for t in trips if t.needs_eta_refresh]
    if not dirty:
        return ReoptResult(actions=(), matrix_calls=travel.matrix_calls, cache_hits=travel.cache_hits)

    if last_run_at is not None:
        elapsed = (now - last_run_at).total_seconds()
        if elapsed < debounce_seconds and len(dirty) < DIRTY_COUNT_FLUSH:
            return ReoptResult(actions=(), matrix_calls=0, cache_hits=0)

    pairs: list[tuple[GeoPoint, GeoPoint]] = []
    meta: list[tuple[ReoptTripInput, list[int]]] = []
    for t in dirty:
        remaining = [s for s in t.stops if not s.completed]
        if not remaining:
            meta.append((t, []))
            continue
        points = [t.live_position] + [GeoPoint(s.lat, s.lng) for s in remaining]
        idxs: list[int] = []
        for a, b in zip(points[:-1], points[1:]):
            idxs.append(len(pairs))
            pairs.append((a, b))
        meta.append((t, idxs))

    durs = travel.batch_durations(pairs, now=now) if pairs else []

    actions: list[ReoptAction] = []
    for t, idxs in meta:
        if not idxs:
            actions.append(ReoptAction(t.trip_id, "none", reason="no_remaining_stops"))
            continue

        remaining = [s for s in t.stops if not s.completed]
        pickup_remaining = [s for s in remaining if s.stop_type == "pickup"]

        total = sum(durs[i] for i in idxs)
        new_drop = now + timedelta(seconds=total)

        new_pickup: datetime | None = None
        if pickup_remaining:
            raw_pickup = now + timedelta(seconds=durs[idxs[0]])
            floor_candidates = [x for x in (t.pickup_ready_at, t.current_eta_pickup) if x is not None]
            floor = max(floor_candidates) if floor_candidates else None
            new_pickup = max(raw_pickup, floor) if floor is not None else raw_pickup
            # Drop must stay after floored pickup (remaining legs after first)
            after_secs = sum(durs[i] for i in idxs[1:]) if len(idxs) > 1 else max(durs[idxs[0]], 60)
            new_drop = max(new_drop, new_pickup + timedelta(seconds=max(after_secs, 60)))

        old_drop = t.current_eta_drop
        drift = 0.0
        if old_drop is not None:
            drift = abs((new_drop - old_drop).total_seconds()) / 60.0

        deadline_risk = False
        cursor = now
        for i, stop in enumerate(remaining):
            cursor = cursor + timedelta(seconds=durs[idxs[i]])
            if stop.deadline_at and cursor > stop.deadline_at:
                deadline_risk = True
                break

        if deadline_risk and not t.boarded_guest_ids:
            actions.append(
                ReoptAction(
                    t.trip_id,
                    "rematch",
                    new_eta_pickup=new_pickup,
                    new_eta_drop=new_drop,
                    drift_minutes=drift,
                    reason="deadline_risk",
                )
            )
        elif drift >= drift_threshold_minutes or deadline_risk:
            if deadline_risk and drift >= drift_threshold_minutes * 2 and not t.boarded_guest_ids:
                actions.append(
                    ReoptAction(
                        t.trip_id,
                        "rematch",
                        new_eta_pickup=new_pickup,
                        new_eta_drop=new_drop,
                        drift_minutes=drift,
                        reason="severe_drift",
                    )
                )
            else:
                actions.append(
                    ReoptAction(
                        t.trip_id,
                        "refresh_eta",
                        new_eta_pickup=new_pickup,
                        new_eta_drop=new_drop,
                        drift_minutes=drift,
                        reason="eta_drift" if drift >= drift_threshold_minutes else "deadline_watch",
                    )
                )
        else:
            actions.append(
                ReoptAction(
                    t.trip_id,
                    "refresh_eta",
                    new_eta_pickup=new_pickup,
                    new_eta_drop=new_drop,
                    drift_minutes=drift,
                    reason="dirty_refresh",
                )
            )

    return ReoptResult(
        actions=tuple(actions),
        matrix_calls=travel.matrix_calls,
        cache_hits=travel.cache_hits,
    )
