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
    """
    travel = travel or CachedTravelProvider(traffic_mode=True)

    dirty = [t for t in trips if t.needs_eta_refresh]
    if not dirty:
        return ReoptResult(actions=(), matrix_calls=travel.matrix_calls, cache_hits=travel.cache_hits)

    if last_run_at is not None:
        elapsed = (now - last_run_at).total_seconds()
        if elapsed < debounce_seconds and len(dirty) < DIRTY_COUNT_FLUSH:
            return ReoptResult(actions=(), matrix_calls=0, cache_hits=0)

    # Batch all consecutive stop pairs across dirty trips
    pairs: list[tuple[GeoPoint, GeoPoint]] = []
    meta: list[tuple[ReoptTripInput, list[int]]] = []  # trip -> indices into pairs
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
        total = sum(durs[i] for i in idxs)
        new_drop = now + timedelta(seconds=total)
        old_drop = t.current_eta_drop
        drift = 0.0
        if old_drop is not None:
            drift = abs((new_drop - old_drop).total_seconds()) / 60.0

        # Deadline risk?
        deadline_risk = False
        cursor = now
        remaining = [s for s in t.stops if not s.completed]
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
                    new_eta_drop=new_drop,
                    drift_minutes=drift,
                    reason="deadline_risk",
                )
            )
        elif drift >= drift_threshold_minutes or deadline_risk:
            # Prefer ETA refresh; rematch only if unboarded and severe
            if deadline_risk and drift >= drift_threshold_minutes * 2:
                actions.append(
                    ReoptAction(
                        t.trip_id,
                        "rematch",
                        new_eta_drop=new_drop,
                        drift_minutes=drift,
                        reason="severe_drift",
                    )
                )
            else:
                # pickup eta ≈ now + first leg
                new_pickup = now + timedelta(seconds=durs[idxs[0]]) if idxs else now
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
