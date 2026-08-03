from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import Guest, Trip, TripGuest
from app.schemas import MatchGuestRequest, TripCreate, TripRead, TripUpdate


def _to_read(trip: Trip) -> TripRead:
    return TripRead(
        id=trip.id,
        trip_type=trip.trip_type,
        status=trip.status,
        driver_id=trip.driver_id,
        origin_location_id=trip.origin_location_id,
        dest_location_id=trip.dest_location_id,
        scheduled_pickup_at=trip.scheduled_pickup_at,
        scheduled_drop_at=trip.scheduled_drop_at,
        eta_pickup=trip.eta_pickup,
        eta_drop=trip.eta_drop,
        seats_used=trip.seats_used,
        luggage_used=trip.luggage_used,
        route_version=trip.route_version,
        party_group_id=trip.party_group_id,
        notes=trip.notes,
        created_at=trip.created_at,
        guest_ids=[tg.guest_id for tg in trip.trip_guests],
    )


def list_trips(db: Session) -> list[TripRead]:
    rows = db.query(Trip).options(joinedload(Trip.trip_guests)).order_by(Trip.created_at.desc()).all()
    return [_to_read(t) for t in rows]


def get_trip(db: Session, trip_id: UUID) -> TripRead:
    trip = db.query(Trip).options(joinedload(Trip.trip_guests)).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _to_read(trip)


def create_trip(db: Session, payload: TripCreate) -> TripRead:
    trip = Trip(
        trip_type=payload.trip_type,
        status=payload.status,
        driver_id=payload.driver_id,
        origin_location_id=payload.origin_location_id,
        dest_location_id=payload.dest_location_id,
        scheduled_pickup_at=payload.scheduled_pickup_at,
        scheduled_drop_at=payload.scheduled_drop_at,
        eta_pickup=payload.eta_pickup,
        eta_drop=payload.eta_drop,
        seats_used=payload.seats_used,
        luggage_used=payload.luggage_used,
        notes=payload.notes,
    )
    db.add(trip)
    db.flush()
    for gid in payload.guest_ids:
        guest = db.query(Guest).filter(Guest.id == gid).first()
        if not guest:
            raise HTTPException(status_code=400, detail=f"Guest {gid} not found")
        db.add(
            TripGuest(
                trip_id=trip.id,
                guest_id=gid,
                seats=guest.party_size,
                luggage=guest.luggage_count,
            )
        )
        if payload.seats_used == 0:
            trip.seats_used += guest.party_size
            trip.luggage_used += guest.luggage_count
    db.commit()
    return get_trip(db, trip.id)


def update_trip(db: Session, trip_id: UUID, payload: TripUpdate) -> TripRead:
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    data = payload.model_dump(exclude_unset=True)
    expected_version = data.pop("route_version", None)
    if expected_version is not None and expected_version != trip.route_version:
        raise HTTPException(
            status_code=409,
            detail=f"route_version conflict: expected {expected_version}, current {trip.route_version}",
        )

    for key, value in data.items():
        setattr(trip, key, value)
    if expected_version is not None:
        trip.route_version = expected_version + 1
    db.commit()
    return get_trip(db, trip_id)


def delete_trip(db: Session, trip_id: UUID) -> None:
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()


def match_guest(db: Session, payload: MatchGuestRequest) -> TripRead:
    """Delegate to matching engine via matching_service (no solver logic here)."""
    from app.services import matching_service

    trips = matching_service.match_guest(db, payload.guest_id)
    return trips[0]
