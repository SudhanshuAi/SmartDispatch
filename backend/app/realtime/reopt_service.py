"""Realtime orchestration: location ingest, live ETA reopt, fan-out + push."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.matching_engine.reopt import DEFAULT_DEBOUNCE_SECONDS, plan_reopt
from app.matching_engine.routing import CachedTravelProvider
from app.matching_engine.types import GeoPoint, ReoptTripInput, StopSnapshot
from app.models import Location, Trip
from app.models.enums import TripStatus
from app.realtime import location_store
from app.realtime.hub import channels_for_trip, hub
from app.realtime.notifications import notify
from app.schemas import DriverLocationUpdate

logger = logging.getLogger(__name__)

ACTIVE = {
    TripStatus.offered,
    TripStatus.accepted,
    TripStatus.en_route,
    TripStatus.at_pickup,
    TripStatus.in_progress,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fire_async(coro) -> None:  # noqa: ANN001
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass


async def _publish(channels: list[str], event: dict) -> None:
    await hub.publish(channels, event)


def ingest_driver_location(
    db: Session,
    driver_id: UUID,
    payload: DriverLocationUpdate,
    *,
    trip_id: UUID | None,
    guest_ids: list[UUID] | None = None,
) -> dict:
    """Write Redis hot location, mark trip dirty, broadcast, optionally reopt."""
    loc = location_store.set_driver_location(
        driver_id,
        lat=payload.lat,
        lng=payload.lng,
        heading=payload.heading,
        speed=payload.speed,
        trip_id=trip_id,
    )
    event = {
        "type": "location",
        "driver_id": str(driver_id),
        "trip_id": str(trip_id) if trip_id else None,
        "lat": payload.lat,
        "lng": payload.lng,
        "ts": loc["ts"],
    }
    channels = ["admin:ops", f"driver:{driver_id}"]
    if trip_id:
        channels.append(f"trip:{trip_id}")
    for gid in guest_ids or []:
        channels.append(f"guest:{gid}")
    _fire_async(_publish(channels, event))

    reopt_summary = None
    if trip_id and _should_run_reopt():
        reopt_summary = apply_live_eta_reopt(db)

    return {"location": loc, "reopt": reopt_summary}


def _should_run_reopt() -> bool:
    last = location_store.get_last_reopt_ts()
    if last is None:
        return True
    return (time.time() - last) >= DEFAULT_DEBOUNCE_SECONDS


def apply_live_eta_reopt(db: Session) -> dict:
    """Run plan_reopt on dirty trips; refresh ETAs; notify on change."""
    dirty_ids = set(location_store.pop_dirty_trips())
    trips = (
        db.query(Trip)
        .options(
            joinedload(Trip.stops),
            joinedload(Trip.trip_guests),
            joinedload(Trip.driver),
        )
        .filter(Trip.status.in_(ACTIVE))
        .all()
    )
    if dirty_ids:
        filtered = [t for t in trips if t.id in dirty_ids]
        if filtered:
            trips = filtered

    now = _now()
    travel = CachedTravelProvider(traffic_mode=True)
    locs = {loc.id: loc for loc in db.query(Location).all()}
    inputs: list[ReoptTripInput] = []
    for t in trips:
        if not t.driver or not t.driver_id:
            continue
        hot = location_store.get_driver_location(t.driver_id)
        if hot:
            live = GeoPoint(hot["lat"], hot["lng"])
        elif t.driver.last_lat is not None and t.driver.last_lng is not None:
            live = GeoPoint(t.driver.last_lat, t.driver.last_lng)
        else:
            continue
        stops = []
        deadlines = []
        for s in sorted(t.stops, key=lambda x: x.sequence):
            loc = locs.get(s.location_id)
            if not loc:
                continue
            stops.append(
                StopSnapshot(
                    location_id=s.location_id,
                    lat=loc.lat,
                    lng=loc.lng,
                    stop_type=s.stop_type.value,
                    guest_id=s.guest_id,
                    sequence=s.sequence,
                    deadline_at=s.deadline_at,
                    completed=s.completed_at is not None,
                )
            )
            deadlines.append(s.deadline_at)
        boarded = tuple(tg.guest_id for tg in t.trip_guests if tg.boarded_at)
        inputs.append(
            ReoptTripInput(
                trip_id=t.id,
                driver_id=t.driver_id,
                route_version=t.route_version,
                needs_eta_refresh=True,
                current_eta_drop=t.eta_drop,
                guest_deadlines=tuple(deadlines),
                boarded_guest_ids=boarded,
                stops=tuple(stops),
                live_position=live,
                seats_used=t.seats_used,
                luggage_used=t.luggage_used,
            )
        )

    last_ts = location_store.get_last_reopt_ts()
    last_run = datetime.fromtimestamp(last_ts, tz=timezone.utc) if last_ts else None
    result = plan_reopt(inputs, now=now, travel=travel, last_run_at=last_run)
    location_store.set_last_reopt_ts()

    refreshed = 0
    for action in result.actions:
        if action.action != "refresh_eta":
            continue
        trip = next((t for t in trips if t.id == action.trip_id), None)
        if not trip:
            continue
        if action.new_eta_pickup is not None:
            trip.eta_pickup = action.new_eta_pickup
        if action.new_eta_drop is not None:
            trip.eta_drop = action.new_eta_drop
        trip.route_version += 1
        refreshed += 1
        guest_ids = [tg.guest_id for tg in trip.trip_guests]
        notify_eta_update(trip, guest_ids, reason=action.reason or "reopt")

    db.commit()
    return {
        "actions": len(result.actions),
        "refreshed": refreshed,
        "matrix_calls": result.matrix_calls,
        "cache_hits": result.cache_hits,
    }


def notify_match(trip: Trip, *, source: str) -> None:
    guest_ids = [tg.guest_id for tg in trip.trip_guests]
    driver_id = trip.driver_id
    audience: list[tuple[str, UUID]] = [("guest", g) for g in guest_ids]
    if driver_id:
        audience.append(("driver", driver_id))
    plate = None
    name = "Driver"
    if trip.driver and trip.driver.vehicle:
        plate = trip.driver.vehicle.plate_number
    if trip.driver and trip.driver.user:
        name = trip.driver.user.full_name
    eta = trip.eta_pickup.isoformat() if trip.eta_pickup else "soon"
    kind = "detour" if source == "detour" else "match"
    title = "Detour assigned" if kind == "detour" else "Driver matched"
    body = f"{name} · {plate or 'vehicle'} · ETA {eta}"
    notify(
        kind=kind,
        title=title,
        body=body,
        audience=audience,
        data={
            "trip_id": str(trip.id),
            "driver_id": str(driver_id) if driver_id else None,
            "eta_pickup": eta,
            "source": source,
        },
    )
    channels = channels_for_trip(trip_id=trip.id, driver_id=driver_id, guest_ids=guest_ids)
    _fire_async(
        _publish(
            channels,
            {
                "type": kind,
                "trip_id": str(trip.id),
                "driver_name": name,
                "vehicle_number": plate,
                "eta_pickup": eta,
                "source": source,
            },
        )
    )


def notify_status_change(trip: Trip, *, action: str) -> None:
    guest_ids = [tg.guest_id for tg in trip.trip_guests]
    audience: list[tuple[str, UUID]] = [("guest", g) for g in guest_ids]
    if trip.driver_id:
        audience.append(("driver", trip.driver_id))
    labels = {
        "arrived_pickup": "Driver arrived at pickup",
        "boarded": "Guest boarded",
        "arrived_drop": "Arrived at destination",
    }
    title = labels.get(action, f"Trip {action}")
    notify(
        kind="status",
        title=title,
        body=f"Trip status → {trip.status.value}",
        audience=audience,
        data={"trip_id": str(trip.id), "action": action, "status": trip.status.value},
    )
    channels = channels_for_trip(trip_id=trip.id, driver_id=trip.driver_id, guest_ids=guest_ids)
    _fire_async(
        _publish(
            channels,
            {"type": "status", "trip_id": str(trip.id), "action": action, "status": trip.status.value},
        )
    )


def notify_eta_update(trip: Trip, guest_ids: list[UUID], *, reason: str) -> None:
    audience: list[tuple[str, UUID]] = [("guest", g) for g in guest_ids]
    if trip.driver_id:
        audience.append(("driver", trip.driver_id))
    eta = trip.eta_pickup.isoformat() if trip.eta_pickup else "—"
    notify(
        kind="eta",
        title="ETA updated",
        body=f"New pickup ETA {eta}",
        audience=audience,
        data={
            "trip_id": str(trip.id),
            "eta_pickup": trip.eta_pickup.isoformat() if trip.eta_pickup else None,
            "eta_drop": trip.eta_drop.isoformat() if trip.eta_drop else None,
            "reason": reason,
        },
    )
    channels = channels_for_trip(trip_id=trip.id, driver_id=trip.driver_id, guest_ids=guest_ids)
    _fire_async(
        _publish(
            channels,
            {
                "type": "eta",
                "trip_id": str(trip.id),
                "eta_pickup": trip.eta_pickup.isoformat() if trip.eta_pickup else None,
                "eta_drop": trip.eta_drop.isoformat() if trip.eta_drop else None,
                "reason": reason,
            },
        )
    )
