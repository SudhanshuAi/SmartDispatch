"""Driver-scoped trip lifecycle, location, and break tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.constants import MANDATORY_BREAK_MINUTES
from app.models import Driver, Guest, Location, LocationPing, Trip, TripGuest
from app.models.enums import DriverStatus, StopType, TripStatus
from app.schemas import DriverLocationUpdate, DriverMeRead, DriverTripView, GuestTripInfo
from app.services import matching_service

ACTIVE_STATUSES = {
    TripStatus.offered,
    TripStatus.accepted,
    TripStatus.en_route,
    TripStatus.at_pickup,
    TripStatus.in_progress,
}

REJECT_COOLDOWN_MINUTES = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_driver(db: Session, driver_id: UUID) -> Driver:
    driver = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .filter(Driver.id == driver_id)
        .first()
    )
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


def _current_trip(db: Session, driver_id: UUID) -> Trip | None:
    return (
        db.query(Trip)
        .options(
            joinedload(Trip.trip_guests).joinedload(TripGuest.guest).joinedload(Guest.user),
            joinedload(Trip.stops),
            joinedload(Trip.origin),
            joinedload(Trip.destination),
        )
        .filter(Trip.driver_id == driver_id, Trip.status.in_(ACTIVE_STATUSES))
        .order_by(Trip.created_at.desc())
        .first()
    )


def _loc_label(loc: Location | None) -> tuple[str | None, str | None, float | None, float | None]:
    if not loc:
        return None, None, None, None
    return loc.name, loc.address, loc.lat, loc.lng


def _trip_view(trip: Trip) -> DriverTripView:
    pickup_name, pickup_addr, plat, plng = _loc_label(trip.origin)
    dest_name, dest_addr, dlat, dlng = _loc_label(trip.destination)
    guests: list[GuestTripInfo] = []
    for tg in trip.trip_guests:
        g = tg.guest
        name = g.user.full_name if g and g.user else "Guest"
        guests.append(
            GuestTripInfo(
                guest_id=tg.guest_id,
                name=name,
                party_size=tg.seats,
                luggage_count=tg.luggage,
                boarded_at=tg.boarded_at,
            )
        )
    return DriverTripView(
        trip_id=trip.id,
        status=trip.status,
        trip_type=trip.trip_type,
        pickup_name=pickup_name,
        pickup_address=pickup_addr,
        pickup_lat=plat,
        pickup_lng=plng,
        dest_name=dest_name,
        dest_address=dest_addr,
        dest_lat=dlat,
        dest_lng=dlng,
        eta_pickup=trip.eta_pickup,
        eta_drop=trip.eta_drop,
        scheduled_pickup_at=trip.scheduled_pickup_at,
        guests=guests,
        seats_used=trip.seats_used,
        luggage_used=trip.luggage_used,
        route_version=trip.route_version,
        notes=trip.notes,
    )


def get_me(db: Session, driver_id: UUID) -> DriverMeRead:
    driver = _get_driver(db, driver_id)
    now = _now()
    on_break = bool(
        driver.status == DriverStatus.on_break
        or (driver.break_until is not None and driver.break_until > now)
    )
    remaining = None
    if driver.break_until and driver.break_until > now:
        remaining = max(0, int((driver.break_until - now).total_seconds()))
    return DriverMeRead(
        driver_id=driver.id,
        full_name=driver.user.full_name if driver.user else "",
        phone=driver.user.phone if driver.user else None,
        status=driver.status,
        plate_number=driver.vehicle.plate_number if driver.vehicle else None,
        seat_capacity=driver.vehicle.seat_capacity if driver.vehicle else None,
        luggage_capacity=driver.vehicle.luggage_capacity if driver.vehicle else None,
        break_until=driver.break_until,
        on_break=on_break,
        break_remaining_seconds=remaining,
        predicted_free_at=driver.predicted_free_at,
        last_lat=driver.last_lat,
        last_lng=driver.last_lng,
        mandatory_break_minutes=MANDATORY_BREAK_MINUTES,
    )


def get_current_trip(db: Session, driver_id: UUID) -> DriverTripView | None:
    # Ensure driver exists / belongs
    _get_driver(db, driver_id)
    trip = _current_trip(db, driver_id)
    if not trip:
        return None
    return _trip_view(trip)


def accept_trip(db: Session, driver_id: UUID) -> DriverTripView:
    driver = _get_driver(db, driver_id)
    trip = _current_trip(db, driver_id)
    if not trip:
        raise HTTPException(status_code=404, detail="No assigned trip")
    if trip.status not in {TripStatus.offered, TripStatus.planned}:
        raise HTTPException(status_code=400, detail=f"Cannot accept status={trip.status.value}")
    if driver.break_until and driver.break_until > _now():
        raise HTTPException(status_code=400, detail="Still on mandatory break/cooldown")

    trip.status = TripStatus.accepted
    trip.route_version += 1
    driver.status = DriverStatus.en_route
    # Move to en_route immediately for ops visibility
    trip.status = TripStatus.en_route
    db.commit()
    return get_current_trip(db, driver_id)  # type: ignore[return-value]


def reject_trip(db: Session, driver_id: UUID, reason: str | None = None) -> dict:
    driver = _get_driver(db, driver_id)
    trip = _current_trip(db, driver_id)
    if not trip:
        raise HTTPException(status_code=404, detail="No assigned trip")
    if trip.status not in {TripStatus.offered, TripStatus.planned, TripStatus.accepted, TripStatus.en_route}:
        raise HTTPException(status_code=400, detail=f"Cannot reject status={trip.status.value}")

    guest_ids = [tg.guest_id for tg in trip.trip_guests]
    trip.status = TripStatus.cancelled
    trip.notes = f"driver_reject; {reason or ''}".strip()
    trip.route_version += 1
    trip.driver_id = None

    now = _now()
    cooldown_until = now + timedelta(minutes=REJECT_COOLDOWN_MINUTES)
    driver.status = DriverStatus.available
    driver.break_until = cooldown_until
    trip_id = trip.id

    db.commit()

    requeued = []
    for gid in guest_ids:
        matching_service.enqueue_ride_request(db, request_id=f"reject-{trip_id}-{gid}", guest_id=gid)
        requeued.append(str(gid))
        try:
            matching_service.match_guest(db, gid)
        except Exception:
            # Stay queued if no feasible driver
            pass

    return {
        "rejected": True,
        "trip_id": str(trip_id),
        "requeued_guests": requeued,
        "cooldown_until": cooldown_until.isoformat(),
    }


def update_trip_status(db: Session, driver_id: UUID, action: str) -> DriverTripView:
    """
    action: arrived_pickup | boarded | arrived_drop
    Feeds halt-time (pickup wait) and free-time/break after drop.
    """
    driver = _get_driver(db, driver_id)
    trip = _current_trip(db, driver_id)
    if not trip:
        raise HTTPException(status_code=404, detail="No assigned trip")
    now = _now()

    if action == "arrived_pickup":
        if trip.status not in {TripStatus.accepted, TripStatus.en_route}:
            raise HTTPException(status_code=400, detail="Trip not en route")
        trip.status = TripStatus.at_pickup
        driver.status = DriverStatus.at_pickup
        # Snap map position to pickup so fleet map shows the driver at the stop
        if trip.origin:
            driver.last_lat = trip.origin.lat
            driver.last_lng = trip.origin.lng
        for stop in trip.stops:
            if stop.stop_type == StopType.pickup and stop.arrived_at is None:
                stop.arrived_at = now
        trip.route_version += 1

    elif action == "boarded":
        if trip.status != TripStatus.at_pickup:
            raise HTTPException(status_code=400, detail="Must arrive at pickup first")
        # Halt time = now - first pickup arrived_at
        halt_secs = 0
        for stop in trip.stops:
            if stop.stop_type == StopType.pickup and stop.arrived_at:
                halt_secs = max(halt_secs, int((now - stop.arrived_at).total_seconds()))
                stop.completed_at = now
        for tg in trip.trip_guests:
            if tg.boarded_at is None:
                tg.boarded_at = now
        trip.status = TripStatus.in_progress
        driver.status = DriverStatus.in_trip
        # Keep at pickup until next GPS ping; ensures in_trip is visible on fleet map
        if trip.origin and (driver.last_lat is None or driver.last_lng is None):
            driver.last_lat = trip.origin.lat
            driver.last_lng = trip.origin.lng
        note = f"halt_seconds={halt_secs}"
        trip.notes = f"{trip.notes + '; ' if trip.notes else ''}{note}"
        trip.route_version += 1

    elif action == "arrived_drop":
        if trip.status not in {TripStatus.in_progress, TripStatus.at_pickup}:
            raise HTTPException(status_code=400, detail="Trip not in progress")
        for stop in trip.stops:
            if stop.stop_type == StopType.drop:
                stop.arrived_at = now
                stop.completed_at = now
        for tg in trip.trip_guests:
            tg.dropped_at = now
        trip.status = TripStatus.completed
        trip.eta_drop = now
        trip.route_version += 1

        # Mandatory break + free-time for matcher
        break_until = now + timedelta(minutes=MANDATORY_BREAK_MINUTES)
        driver.status = DriverStatus.on_break
        driver.break_until = break_until
        driver.predicted_free_at = break_until
        if trip.destination:
            driver.predicted_free_lat = trip.destination.lat
            driver.predicted_free_lng = trip.destination.lng
            driver.last_lat = trip.destination.lat
            driver.last_lng = trip.destination.lng
        trip.notes = f"{trip.notes + '; ' if trip.notes else ''}break_until={break_until.isoformat()}"

    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    db.commit()

    from app.realtime.reopt_service import notify_status_change

    # Reload with guests for notify
    trip = (
        db.query(Trip)
        .options(joinedload(Trip.trip_guests))
        .filter(Trip.id == trip.id)
        .one()
    )
    notify_status_change(trip, action=action)

    # Completed trips no longer "current"
    if action == "arrived_drop":
        return DriverTripView(
            trip_id=trip.id,
            status=trip.status,
            trip_type=trip.trip_type,
            pickup_name=trip.origin.name if trip.origin else None,
            pickup_address=trip.origin.address if trip.origin else None,
            pickup_lat=trip.origin.lat if trip.origin else None,
            pickup_lng=trip.origin.lng if trip.origin else None,
            dest_name=trip.destination.name if trip.destination else None,
            dest_address=trip.destination.address if trip.destination else None,
            dest_lat=trip.destination.lat if trip.destination else None,
            dest_lng=trip.destination.lng if trip.destination else None,
            eta_pickup=trip.eta_pickup,
            eta_drop=trip.eta_drop,
            scheduled_pickup_at=trip.scheduled_pickup_at,
            guests=[],
            seats_used=trip.seats_used,
            luggage_used=trip.luggage_used,
            route_version=trip.route_version,
            notes=trip.notes,
        )
    return get_current_trip(db, driver_id)  # type: ignore[return-value]


def update_location(db: Session, driver_id: UUID, payload: DriverLocationUpdate) -> dict:
    driver = _get_driver(db, driver_id)
    trip = _current_trip(db, driver_id)
    if not trip:
        raise HTTPException(status_code=400, detail="Location sharing only while on a trip")
    if driver.status not in {
        DriverStatus.en_route,
        DriverStatus.at_pickup,
        DriverStatus.in_trip,
    }:
        raise HTTPException(status_code=400, detail="Driver not in an active trip state")

    now = _now()
    driver.last_lat = payload.lat
    driver.last_lng = payload.lng
    db.add(
        LocationPing(
            driver_id=driver.id,
            lat=payload.lat,
            lng=payload.lng,
            heading=payload.heading,
            speed=payload.speed,
            recorded_at=now,
        )
    )
    db.commit()

    from app.realtime.reopt_service import ingest_driver_location

    guest_ids = [tg.guest_id for tg in trip.trip_guests]
    realtime = ingest_driver_location(
        db,
        driver_id,
        payload,
        trip_id=trip.id,
        guest_ids=guest_ids,
    )
    return {
        "ok": True,
        "driver_id": str(driver.id),
        "lat": payload.lat,
        "lng": payload.lng,
        "recorded_at": now.isoformat(),
        "trip_id": str(trip.id),
        "realtime": realtime,
    }


def end_break(db: Session, driver_id: UUID) -> DriverMeRead:
    """Allow returning to available only after break_until has passed."""
    driver = _get_driver(db, driver_id)
    now = _now()
    if driver.break_until and driver.break_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Break until {driver.break_until.isoformat()}",
        )
    driver.status = DriverStatus.available
    driver.break_until = None
    db.commit()
    return get_me(db, driver_id)
