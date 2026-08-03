"""Ops dashboard + ride requests + override helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import AssignmentEvent, Driver, Guest, Location, RideRequest, Trip, TripGuest, User, Vehicle
from app.models.enums import (
    AssignmentSource,
    DriverStatus,
    RideRequestStatus,
    TripStatus,
    TripType,
    UserRole,
)
from app.schemas import (
    DashboardSnapshot,
    DriverDashboardRow,
    DriverOnboardRequest,
    DriverRead,
    ForceMatchRequest,
    GuestCreate,
    GuestDashboardRow,
    GuestRead,
    LocationRead,
    MarkVehicleDownRequest,
    ReassignTripRequest,
    RideRequestCreate,
    RideRequestRead,
)
from app.services import matching_service
from app.services.driver_service import _to_read as driver_to_read
from app.services.guest_service import _to_read as guest_to_read
from app.services.guest_service import create_guest
from app.services.security import hash_password
from app.services.trip_service import _to_read as trip_to_read


def list_locations(db: Session) -> list[LocationRead]:
    rows = db.query(Location).order_by(Location.type, Location.name).all()
    return [LocationRead.model_validate(r) for r in rows]


def list_ride_requests(db: Session, status: RideRequestStatus | None = None) -> list[RideRequestRead]:
    q = db.query(RideRequest).options(joinedload(RideRequest.guest).joinedload(Guest.user))
    if status:
        q = q.filter(RideRequest.status == status)
    rows = q.order_by(RideRequest.created_at.desc()).all()
    return [_ride_to_read(r) for r in rows]


def create_ride_request(db: Session, payload: RideRequestCreate) -> RideRequestRead:
    guest = db.query(Guest).filter(Guest.id == payload.guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    origin = payload.origin_location_id or guest.pickup_location_id
    dest = payload.dest_location_id or guest.accommodation_id
    if not origin or not dest:
        raise HTTPException(status_code=400, detail="Missing origin/destination")
    rr = RideRequest(
        guest_id=guest.id,
        origin_location_id=origin,
        dest_location_id=dest,
        party_size=payload.party_size or guest.party_size,
        luggage_count=payload.luggage_count if payload.luggage_count is not None else guest.luggage_count,
        status=RideRequestStatus.pending_admin,
        wait_started_at=datetime.now(timezone.utc),
    )
    db.add(rr)
    db.commit()
    loaded = (
        db.query(RideRequest)
        .options(joinedload(RideRequest.guest).joinedload(Guest.user))
        .filter(RideRequest.id == rr.id)
        .one()
    )
    return _ride_to_read(loaded)


def approve_ride_request(db: Session, request_id: UUID, admin_user_id: UUID | None = None) -> dict:
    """Manual approve → matching engine allocates (admin does not pick driver)."""
    rr = db.query(RideRequest).filter(RideRequest.id == request_id).first()
    if not rr:
        raise HTTPException(status_code=404, detail="Ride request not found")
    if rr.status != RideRequestStatus.pending_admin:
        raise HTTPException(status_code=400, detail=f"Cannot approve status={rr.status.value}")

    rr.status = RideRequestStatus.approved
    rr.approved_by = admin_user_id
    db.commit()

    guest = db.query(Guest).filter(Guest.id == rr.guest_id).first()
    if guest:
        guest.pickup_location_id = rr.origin_location_id
        guest.accommodation_id = rr.dest_location_id
        guest.party_size = rr.party_size
        guest.luggage_count = rr.luggage_count
        db.commit()

    matching_service.enqueue_ride_request(
        db,
        request_id=str(rr.id),
        guest_id=rr.guest_id,
        wait_started_at=rr.wait_started_at,
    )
    try:
        trips = matching_service.match_guest(db, rr.guest_id)
        rr.status = RideRequestStatus.matched
        rr.trip_id = trips[0].id
        db.commit()
        return {
            "status": "matched",
            "ride_request_id": str(rr.id),
            "trip_ids": [str(t.id) for t in trips],
            "message": "Approved — matching engine assigned driver(s).",
        }
    except HTTPException as exc:
        rr.status = RideRequestStatus.queued
        db.commit()
        return {
            "status": "queued",
            "ride_request_id": str(rr.id),
            "detail": str(exc.detail),
            "message": "Approved — queued for rematch (no feasible driver or matching engine unavailable).",
        }


def decline_ride_request(db: Session, request_id: UUID) -> RideRequestRead:
    rr = (
        db.query(RideRequest)
        .options(joinedload(RideRequest.guest).joinedload(Guest.user))
        .filter(RideRequest.id == request_id)
        .first()
    )
    if not rr:
        raise HTTPException(status_code=404, detail="Ride request not found")
    if rr.status != RideRequestStatus.pending_admin:
        raise HTTPException(status_code=400, detail=f"Cannot decline status={rr.status.value}")
    rr.status = RideRequestStatus.declined
    db.commit()
    db.refresh(rr)
    return _ride_to_read(rr)


def onboard_driver(db: Session, payload: DriverOnboardRequest) -> DriverRead:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(Vehicle).filter(Vehicle.plate_number == payload.plate_number).first():
        raise HTTPException(status_code=400, detail="Plate number already exists")

    vehicle = Vehicle(
        plate_number=payload.plate_number,
        seat_capacity=payload.seat_capacity,
        luggage_capacity=payload.luggage_capacity,
        make_model=payload.make_model,
    )
    db.add(vehicle)
    db.flush()
    user = User(
        email=payload.email,
        role=UserRole.driver,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
    )
    db.add(user)
    db.flush()
    driver = Driver(
        user_id=user.id,
        vehicle_id=vehicle.id,
        status=DriverStatus.available,
        last_lat=payload.last_lat,
        last_lng=payload.last_lng,
    )
    db.add(driver)
    db.commit()
    return driver_to_read(
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .filter(Driver.id == driver.id)
        .one()
    )


def create_walk_in_guest(db: Session, payload: GuestCreate) -> GuestRead:
    return create_guest(db, payload)


def reassign_trip(db: Session, payload: ReassignTripRequest) -> dict:
    trip = db.query(Trip).filter(Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if payload.expected_route_version is not None and trip.route_version != payload.expected_route_version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"route_version conflict: expected {payload.expected_route_version}, "
                f"current {trip.route_version}"
            ),
        )
    driver = db.query(Driver).filter(Driver.id == payload.new_driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    trip.driver_id = payload.new_driver_id
    trip.route_version += 1
    trip.notes = f"override reassign; {payload.reason or ''}".strip()
    db.add(
        AssignmentEvent(
            trip_id=trip.id,
            driver_id=payload.new_driver_id,
            source=AssignmentSource.override,
            detail=payload.reason or "manual_reassign",
        )
    )
    db.commit()
    return {"trip_id": str(trip.id), "driver_id": str(payload.new_driver_id), "route_version": trip.route_version}


def mark_vehicle_down(db: Session, payload: MarkVehicleDownRequest) -> DriverRead:
    driver = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .filter(Driver.id == payload.driver_id)
        .first()
    )
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    driver.status = DriverStatus.offline
    open_trips = (
        db.query(Trip)
        .options(joinedload(Trip.trip_guests))
        .filter(
            Trip.driver_id == driver.id,
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
        .all()
    )
    for trip in open_trips:
        trip.status = TripStatus.cancelled
        trip.notes = f"vehicle_down; {payload.reason or ''}".strip()
        trip.route_version += 1
        for tg in trip.trip_guests:
            try:
                matching_service.enqueue_ride_request(
                    db, request_id=f"requeue-{tg.guest_id}", guest_id=tg.guest_id
                )
            except Exception:
                # Engine/queue down: trip still cancelled; rematch when engine recovers
                pass
        db.add(
            AssignmentEvent(
                trip_id=trip.id,
                driver_id=driver.id,
                source=AssignmentSource.override,
                detail=payload.reason or "vehicle_down",
            )
        )
    db.commit()
    return driver_to_read(driver)


def force_match(db: Session, payload: ForceMatchRequest) -> dict:
    guest = db.query(Guest).filter(Guest.id == payload.guest_id).first()
    driver = db.query(Driver).options(joinedload(Driver.vehicle)).filter(Driver.id == payload.driver_id).first()
    if not guest or not driver:
        raise HTTPException(status_code=404, detail="Guest or driver not found")
    if not guest.pickup_location_id or not guest.accommodation_id:
        raise HTTPException(status_code=400, detail="Guest missing locations")

    trip = Trip(
        trip_type=TripType.on_demand,
        status=TripStatus.offered,
        driver_id=driver.id,
        origin_location_id=guest.pickup_location_id,
        dest_location_id=guest.accommodation_id,
        scheduled_pickup_at=guest.travel_eta,
        seats_used=guest.party_size,
        luggage_used=guest.luggage_count,
        notes=f"override force-match; {payload.reason or ''}".strip(),
        route_version=1,
    )
    db.add(trip)
    db.flush()
    db.add(
        TripGuest(
            trip_id=trip.id,
            guest_id=guest.id,
            seats=guest.party_size,
            luggage=guest.luggage_count,
        )
    )
    db.add(
        AssignmentEvent(
            trip_id=trip.id,
            guest_id=guest.id,
            driver_id=driver.id,
            source=AssignmentSource.override,
            detail=payload.reason or "force_match",
        )
    )
    db.commit()
    return {"trip_id": str(trip.id), "driver_id": str(driver.id), "guest_id": str(guest.id)}


def dashboard_snapshot(db: Session) -> DashboardSnapshot:
    drivers = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .order_by(Driver.created_at)
        .all()
    )
    guests = db.query(Guest).options(joinedload(Guest.user)).order_by(Guest.travel_eta).all()
    trips = (
        db.query(Trip)
        .options(joinedload(Trip.trip_guests))
        .filter(Trip.status != TripStatus.cancelled)
        .order_by(Trip.created_at.desc())
        .limit(200)
        .all()
    )
    pending = (
        db.query(RideRequest)
        .options(joinedload(RideRequest.guest).joinedload(Guest.user))
        .filter(RideRequest.status == RideRequestStatus.pending_admin)
        .order_by(RideRequest.created_at)
        .all()
    )

    assigned_guest_ids: set[UUID] = set()
    in_transit_guest_ids: set[UUID] = set()
    trip_by_driver: dict[UUID, Trip] = {}
    for t in trips:
        if t.driver_id and t.status in {
            TripStatus.offered,
            TripStatus.accepted,
            TripStatus.en_route,
            TripStatus.at_pickup,
            TripStatus.in_progress,
        }:
            trip_by_driver[t.driver_id] = t
        for tg in t.trip_guests:
            if t.status in {TripStatus.offered, TripStatus.accepted, TripStatus.planned}:
                assigned_guest_ids.add(tg.guest_id)
            if t.status in {TripStatus.en_route, TripStatus.at_pickup, TripStatus.in_progress}:
                in_transit_guest_ids.add(tg.guest_id)
                assigned_guest_ids.discard(tg.guest_id)

    guest_states = []
    for g in guests:
        if g.id in in_transit_guest_ids:
            state = "in_transit"
        elif g.id in assigned_guest_ids:
            state = "assigned"
        else:
            state = "waiting"
        guest_states.append(GuestDashboardRow(guest=guest_to_read(g), state=state))

    driver_rows = []
    for d in drivers:
        t = trip_by_driver.get(d.id)
        driver_rows.append(
            DriverDashboardRow(
                driver=driver_to_read(d),
                current_trip=trip_to_read(t) if t else None,
            )
        )

    return DashboardSnapshot(
        drivers=driver_rows,
        guests=guest_states,
        pending_ride_requests=[_ride_to_read(r) for r in pending],
        active_trips=[
            trip_to_read(t)
            for t in trips
            if t.status not in {TripStatus.completed, TripStatus.cancelled}
        ],
        counts={
            "drivers_available": sum(1 for d in drivers if d.status == DriverStatus.available),
            "drivers_total": len(drivers),
            "guests_waiting": sum(1 for g in guest_states if g.state == "waiting"),
            "guests_assigned": sum(1 for g in guest_states if g.state == "assigned"),
            "guests_in_transit": sum(1 for g in guest_states if g.state == "in_transit"),
            "pending_requests": len(pending),
        },
    )


def seed_demo_ride_requests(db: Session, n: int = 5) -> list[RideRequestRead]:
    guests = db.query(Guest).order_by(Guest.travel_eta).limit(n * 3).all()
    created: list[RideRequestRead] = []
    for g in guests:
        if len(created) >= n:
            break
        if not g.pickup_location_id or not g.accommodation_id:
            continue
        existing = (
            db.query(RideRequest)
            .filter(
                RideRequest.guest_id == g.id,
                RideRequest.status == RideRequestStatus.pending_admin,
            )
            .first()
        )
        if existing:
            continue
        created.append(
            create_ride_request(
                db,
                RideRequestCreate(
                    guest_id=g.id,
                    origin_location_id=g.pickup_location_id,
                    dest_location_id=g.accommodation_id,
                    party_size=g.party_size,
                    luggage_count=g.luggage_count,
                ),
            )
        )
    return created


def stub_login(db: Session, email: str) -> dict:
    user = (
        db.query(User)
        .options(joinedload(User.driver), joinedload(User.guest))
        .filter(User.email == email)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    driver_id = None
    guest_id = None
    if user.role == UserRole.driver and user.driver:
        driver_id = str(user.driver.id)
    if user.role == UserRole.guest and user.guest:
        guest_id = str(user.guest.id)
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "driver_id": driver_id,
        "guest_id": guest_id,
        "token": f"stub-{user.role.value}-{user.id}",
    }


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
