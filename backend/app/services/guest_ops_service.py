"""Guest-scoped pickup, match, and on-demand ride request APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import Driver, Guest, Location, RideRequest, Trip, TripGuest
from app.models.enums import RideRequestStatus, TripStatus
from app.schemas import (
    GuestLocationRead,
    GuestMatchView,
    GuestMeRead,
    GuestRideRequestCreate,
    RideRequestRead,
)

ACTIVE_TRIP = {
    TripStatus.offered,
    TripStatus.accepted,
    TripStatus.en_route,
    TripStatus.at_pickup,
    TripStatus.in_progress,
}

# Explicitly never shown on Guest "Your ride"
ENDED_TRIP = {TripStatus.completed, TripStatus.cancelled}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_guest(db: Session, guest_id: UUID) -> Guest:
    guest = (
        db.query(Guest)
        .options(
            joinedload(Guest.user),
            joinedload(Guest.pickup_location),
            joinedload(Guest.accommodation),
        )
        .filter(Guest.id == guest_id)
        .first()
    )
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest


def _loc_read(loc: Location | None) -> GuestLocationRead | None:
    if not loc:
        return None
    return GuestLocationRead(
        id=loc.id,
        name=loc.name,
        type=loc.type,
        address=loc.address,
        lat=loc.lat,
        lng=loc.lng,
    )


def get_me(db: Session, guest_id: UUID) -> GuestMeRead:
    g = _get_guest(db, guest_id)
    return GuestMeRead(
        guest_id=g.id,
        full_name=g.user.full_name if g.user else "",
        email=g.user.email if g.user else None,
        phone=g.user.phone if g.user else None,
        party_size=g.party_size,
        luggage_count=g.luggage_count,
        travel_eta=g.travel_eta,
        travel_mode=g.travel_mode,
        travel_ref=g.travel_ref,
        attendance_status=g.attendance_status,
        pickup=_loc_read(g.pickup_location),
        accommodation=_loc_read(g.accommodation),
    )


def list_locations(db: Session) -> list[GuestLocationRead]:
    """Event locations only — never drivers."""
    rows = db.query(Location).order_by(Location.name).all()
    return [
        GuestLocationRead(id=r.id, name=r.name, type=r.type, address=r.address, lat=r.lat, lng=r.lng)
        for r in rows
    ]


def _active_trip_for_guest(db: Session, guest_id: UUID) -> Trip | None:
    return (
        db.query(Trip)
        .join(TripGuest, TripGuest.trip_id == Trip.id)
        .options(
            joinedload(Trip.driver).joinedload(Driver.user),
            joinedload(Trip.driver).joinedload(Driver.vehicle),
            joinedload(Trip.origin),
            joinedload(Trip.destination),
            joinedload(Trip.trip_guests),
        )
        .filter(TripGuest.guest_id == guest_id, Trip.status.in_(ACTIVE_TRIP))
        .order_by(Trip.created_at.desc())
        .first()
    )


def get_match(db: Session, guest_id: UUID) -> GuestMatchView | None:
    """Passive match payload — no driver browsing. Completed/cancelled trips return None."""
    _get_guest(db, guest_id)
    trip = _active_trip_for_guest(db, guest_id)
    if not trip or not trip.driver:
        return None
    if trip.status in ENDED_TRIP:
        return None
    d = trip.driver
    from app.realtime import location_store

    hot = location_store.get_driver_location(d.id)
    driver_lat = hot["lat"] if hot else d.last_lat
    driver_lng = hot["lng"] if hot else d.last_lng
    return GuestMatchView(
        matched=True,
        trip_id=trip.id,
        trip_status=trip.status,
        trip_type=trip.trip_type,
        driver_name=d.user.full_name if d.user else "Driver",
        vehicle_number=d.vehicle.plate_number if d.vehicle else None,
        vehicle_make_model=d.vehicle.make_model if d.vehicle else None,
        eta_pickup=trip.eta_pickup,
        eta_drop=trip.eta_drop,
        driver_lat=driver_lat,
        driver_lng=driver_lng,
        pickup=_loc_read(trip.origin),
        destination=_loc_read(trip.destination),
        route_version=trip.route_version,
        notified_at=_now(),
    )


def create_ride_request(db: Session, guest_id: UUID, payload: GuestRideRequestCreate) -> RideRequestRead:
    guest = _get_guest(db, guest_id)
    origin_id = payload.origin_location_id or guest.pickup_location_id
    dest_id = payload.dest_location_id or guest.accommodation_id
    if not origin_id or not dest_id:
        raise HTTPException(status_code=400, detail="Origin and destination required")

    # One open pending request at a time
    existing = (
        db.query(RideRequest)
        .filter(
            RideRequest.guest_id == guest_id,
            RideRequest.status == RideRequestStatus.pending_admin,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="You already have a pending ride request")

    # Block while an active trip is already assigned
    active = (
        db.query(TripGuest)
        .join(Trip, Trip.id == TripGuest.trip_id)
        .filter(
            TripGuest.guest_id == guest_id,
            Trip.status.in_(
                [
                    TripStatus.planned,
                    TripStatus.offered,
                    TripStatus.accepted,
                    TripStatus.en_route,
                    TripStatus.at_pickup,
                    TripStatus.in_progress,
                ]
            ),
        )
        .first()
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail="You already have an active trip — wait until it completes before requesting again",
        )

    # Hide prior demo/test noise: supersede old matched/queued rows without an active trip
    stale = (
        db.query(RideRequest)
        .filter(
            RideRequest.guest_id == guest_id,
            RideRequest.status.in_(
                [
                    RideRequestStatus.matched,
                    RideRequestStatus.approved,
                    RideRequestStatus.queued,
                ]
            ),
        )
        .all()
    )
    for old in stale:
        old.status = RideRequestStatus.cancelled

    rr = RideRequest(
        guest_id=guest_id,
        origin_location_id=origin_id,
        dest_location_id=dest_id,
        party_size=payload.party_size or guest.party_size,
        luggage_count=payload.luggage_count if payload.luggage_count is not None else guest.luggage_count,
        status=RideRequestStatus.pending_admin,
        wait_started_at=_now(),
        priority_score=0.0,
    )
    db.add(rr)
    db.commit()
    db.refresh(rr)
    rr = (
        db.query(RideRequest)
        .options(joinedload(RideRequest.guest).joinedload(Guest.user))
        .filter(RideRequest.id == rr.id)
        .one()
    )
    return _ride_to_read(rr)


def list_my_ride_requests(db: Session, guest_id: UUID) -> list[RideRequestRead]:
    _get_guest(db, guest_id)
    rows = (
        db.query(RideRequest)
        .options(joinedload(RideRequest.guest).joinedload(Guest.user))
        .filter(
            RideRequest.guest_id == guest_id,
            RideRequest.status != RideRequestStatus.cancelled,
        )
        .order_by(RideRequest.created_at.desc())
        .limit(10)
        .all()
    )
    return [_ride_to_read(r) for r in rows]


def _ride_to_read(rr: RideRequest) -> RideRequestRead:
    guest_name = None
    if rr.guest and rr.guest.user:
        guest_name = rr.guest.user.full_name
    return RideRequestRead(
        id=rr.id,
        guest_id=rr.guest_id,
        guest_name=guest_name,
        origin_location_id=rr.origin_location_id,
        dest_location_id=rr.dest_location_id,
        party_size=rr.party_size,
        luggage_count=rr.luggage_count,
        status=rr.status,
        wait_started_at=rr.wait_started_at,
        priority_score=rr.priority_score,
        trip_id=rr.trip_id,
        created_at=rr.created_at,
    )
