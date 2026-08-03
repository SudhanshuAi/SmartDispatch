"""Build matching snapshots from ORM and apply ProposedTrip results."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.matching_engine import DispatchMatchingEngine, InMemoryPriorityQueue
from app.matching_engine.priority_queue import RedisPriorityQueue
from app.matching_engine.types import (
    ActiveTripSnapshot,
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    ProposedTrip,
    QueueItem,
    StopSnapshot,
)
from app.models import AssignmentEvent, Driver, Guest, Location, Trip, TripGuest, TripStop
from app.models.enums import AssignmentSource, StopType, TripStatus, TripType
from app.realtime import location_store
from app.realtime.reopt_service import notify_match
from app.redis_client import get_redis
from app.config import get_settings
from app.schemas import TripRead
from app.services import trip_service

_engine = DispatchMatchingEngine()


class MatchingEngineUnavailable(HTTPException):
    def __init__(self, detail: str = "Matching engine unavailable") -> None:
        super().__init__(status_code=503, detail=detail)


def _ensure_engine_enabled() -> None:
    if not get_settings().matching_engine_enabled:
        raise MatchingEngineUnavailable("Matching engine disabled — in-progress trips and admin overrides still work")


def _build_match_queue():
    r = get_redis()
    if r is not None:
        return RedisPriorityQueue(r)
    return InMemoryPriorityQueue()


_match_queue = _build_match_queue()


def get_match_queue():
    """Expose queue for admin/metrics; rebuild if Redis recovered after cold start."""
    global _match_queue
    if isinstance(_match_queue, InMemoryPriorityQueue):
        r = get_redis()
        if r is not None:
            _match_queue = RedisPriorityQueue(r)
    return _match_queue

def _tz_now() -> datetime:
    return datetime.now(timezone.utc)


def _loc_map(db: Session) -> dict[UUID, GeoPoint]:
    return {loc.id: GeoPoint(loc.lat, loc.lng) for loc in db.query(Location).all()}


def _guest_snap(g: Guest) -> GuestSnapshot:
    if not g.pickup_location_id or not g.accommodation_id:
        raise HTTPException(status_code=400, detail="Guest missing pickup or accommodation")
    ready = g.travel_eta or _tz_now()
    deadline = ready + timedelta(minutes=45)
    return GuestSnapshot(
        guest_id=g.id,
        party_size=g.party_size,
        luggage_count=g.luggage_count,
        pickup_location_id=g.pickup_location_id,
        drop_location_id=g.accommodation_id,
        ready_at=ready,
        deadline_at=deadline,
        priority=g.priority,
    )


def _driver_snaps(db: Session) -> list[DriverSnapshot]:
    drivers = db.query(Driver).options(joinedload(Driver.vehicle)).all()
    active_trips = (
        db.query(Trip)
        .options(joinedload(Trip.stops), joinedload(Trip.trip_guests))
        .filter(
            Trip.status.in_(
                [
                    TripStatus.offered,
                    TripStatus.accepted,
                    TripStatus.en_route,
                    TripStatus.at_pickup,
                    TripStatus.in_progress,
                ]
            )
        )
        .all()
    )
    trip_by_driver = {t.driver_id: t for t in active_trips if t.driver_id}

    locs = {loc.id: loc for loc in db.query(Location).all()}
    out: list[DriverSnapshot] = []
    for d in drivers:
        if not d.vehicle:
            continue
        depot = GeoPoint(
            d.last_lat if d.last_lat is not None else 28.6139,
            d.last_lng if d.last_lng is not None else 77.2090,
        )
        live = (
            GeoPoint(d.last_lat, d.last_lng)
            if d.last_lat is not None and d.last_lng is not None
            else depot
        )
        hot = location_store.get_driver_location(d.id)
        if hot:
            live = GeoPoint(hot["lat"], hot["lng"])
        cur = None
        t = trip_by_driver.get(d.id)
        if t:
            stops = []
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
            cur = ActiveTripSnapshot(
                trip_id=t.id,
                route_version=t.route_version,
                seats_used=t.seats_used,
                luggage_used=t.luggage_used,
                trip_type=t.trip_type.value,
                stops=tuple(stops),
                locked_by_override=("override" in (t.notes or "").lower()),
            )
        out.append(
            DriverSnapshot(
                driver_id=d.id,
                vehicle_id=d.vehicle_id,
                seat_capacity=d.vehicle.seat_capacity,
                luggage_capacity=d.vehicle.luggage_capacity,
                status=d.status.value,
                break_until=d.break_until,
                live_position=live,
                predicted_free_at=d.predicted_free_at,
                predicted_free_position=(
                    GeoPoint(d.predicted_free_lat, d.predicted_free_lng)
                    if d.predicted_free_lat is not None and d.predicted_free_lng is not None
                    else None
                ),
                depot=depot,
                current_trip=cur,
            )
        )
    return out


def _source_enum(source: str) -> AssignmentSource:
    mapping = {
        "batch": AssignmentSource.batch,
        "greedy": AssignmentSource.greedy,
        "greedy_split": AssignmentSource.greedy,
        "detour": AssignmentSource.detour,
    }
    return mapping.get(source, AssignmentSource.greedy)


def apply_proposed_trip(db: Session, proposal: ProposedTrip) -> Trip:
    if proposal.existing_trip_id is not None:
        trip = db.query(Trip).filter(Trip.id == proposal.existing_trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found for detour")
        if proposal.expected_route_version is not None and trip.route_version != proposal.expected_route_version:
            raise HTTPException(
                status_code=409,
                detail=f"route_version conflict: expected {proposal.expected_route_version}, current {trip.route_version}",
            )
        trip.seats_used = proposal.seats_used
        trip.luggage_used = proposal.luggage_used
        trip.eta_pickup = proposal.eta_pickup
        trip.eta_drop = proposal.eta_drop
        trip.notes = proposal.notes
        trip.route_version = trip.route_version + 1
        # Replace stops
        for s in list(trip.stops):
            db.delete(s)
        db.flush()
        for ps in proposal.stops:
            db.add(
                TripStop(
                    trip_id=trip.id,
                    guest_id=ps.guest_id,
                    location_id=ps.location_id,
                    sequence=ps.sequence,
                    stop_type=StopType(ps.stop_type),
                    deadline_at=ps.deadline_at,
                )
            )
        existing_guests = {tg.guest_id for tg in trip.trip_guests}
        for gid in proposal.guest_ids:
            if gid not in existing_guests:
                g = db.query(Guest).filter(Guest.id == gid).first()
                db.add(
                    TripGuest(
                        trip_id=trip.id,
                        guest_id=gid,
                        seats=g.party_size if g else 1,
                        luggage=g.luggage_count if g else 0,
                    )
                )
        db.add(
            AssignmentEvent(
                trip_id=trip.id,
                guest_id=proposal.guest_ids[-1] if proposal.guest_ids else None,
                driver_id=proposal.driver_id,
                source=_source_enum(proposal.source),
                detail=proposal.notes,
            )
        )
        db.commit()
        trip = (
            db.query(Trip)
            .options(
                joinedload(Trip.trip_guests),
                joinedload(Trip.driver).joinedload(Driver.user),
                joinedload(Trip.driver).joinedload(Driver.vehicle),
            )
            .filter(Trip.id == trip.id)
            .one()
        )
        notify_match(trip, source=proposal.source)
        return trip

    trip = Trip(
        trip_type=TripType(proposal.trip_type),
        status=TripStatus.offered,
        driver_id=proposal.driver_id,
        origin_location_id=proposal.origin_location_id,
        dest_location_id=proposal.dest_location_id,
        scheduled_pickup_at=proposal.scheduled_pickup_at,
        eta_pickup=proposal.eta_pickup,
        eta_drop=proposal.eta_drop,
        seats_used=proposal.seats_used,
        luggage_used=proposal.luggage_used,
        party_group_id=proposal.party_group_id,
        notes=proposal.notes or proposal.source,
        route_version=1,
    )
    db.add(trip)
    db.flush()
    for gid in proposal.guest_ids:
        g = db.query(Guest).filter(Guest.id == gid).first()
        db.add(
            TripGuest(
                trip_id=trip.id,
                guest_id=gid,
                seats=proposal.seats_used if len(proposal.guest_ids) == 1 else (g.party_size if g else 1),
                luggage=proposal.luggage_used if len(proposal.guest_ids) == 1 else (g.luggage_count if g else 0),
            )
        )
    for ps in proposal.stops:
        db.add(
            TripStop(
                trip_id=trip.id,
                guest_id=ps.guest_id,
                location_id=ps.location_id,
                sequence=ps.sequence,
                stop_type=StopType(ps.stop_type),
                deadline_at=ps.deadline_at,
            )
        )
    db.add(
        AssignmentEvent(
            trip_id=trip.id,
            guest_id=proposal.guest_ids[0] if proposal.guest_ids else None,
            driver_id=proposal.driver_id,
            source=_source_enum(proposal.source),
            detail=proposal.notes,
        )
    )
    db.commit()
    trip = (
        db.query(Trip)
        .options(
            joinedload(Trip.trip_guests),
            joinedload(Trip.driver).joinedload(Driver.user),
            joinedload(Trip.driver).joinedload(Driver.vehicle),
        )
        .filter(Trip.id == trip.id)
        .one()
    )
    # Mark driver busy for subsequent matches in same process
    if trip.driver_id:
        drv = db.query(Driver).filter(Driver.id == trip.driver_id).first()
        if drv and drv.status.value == "available":
            from app.models.enums import DriverStatus

            drv.status = DriverStatus.en_route
            db.commit()
    notify_match(trip, source=proposal.source)
    return trip


def match_guest(db: Session, guest_id: UUID) -> list[TripRead]:
    """Allocate driver(s) for one guest. Never mutates unrelated in-progress trips."""
    _ensure_engine_enabled()
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    snap = _guest_snap(guest)
    try:
        result = _engine.match_one(snap, _driver_snaps(db), _loc_map(db), now=_tz_now())
    except HTTPException:
        raise
    except Exception as exc:
        raise MatchingEngineUnavailable(f"Matching engine error: {exc}") from exc
    if not result.matched:
        reason = result.unmatched.reason.value if result.unmatched else "no_feasible_driver"
        raise HTTPException(status_code=409, detail=reason)

    reads: list[TripRead] = []
    for proposal in result.all_trips():
        trip = apply_proposed_trip(db, proposal)
        reads.append(trip_service.get_trip(db, trip.id))
    return reads


def run_batch_assignment(db: Session, *, limit: int | None = None) -> dict:
    _ensure_engine_enabled()
    q = db.query(Guest).filter(Guest.travel_eta.isnot(None)).order_by(Guest.travel_eta)
    if limit is not None:
        q = q.limit(limit)
    guests = q.all()
    snaps = []
    for g in guests:
        try:
            snaps.append(_guest_snap(g))
        except HTTPException:
            continue
    # Fresh travel cache per batch run (planning TTL)
    from app.matching_engine.routing import CachedTravelProvider

    engine = DispatchMatchingEngine(travel=CachedTravelProvider(traffic_mode=False))
    try:
        result = engine.run_batch(snaps, _driver_snaps(db), _loc_map(db), now=_tz_now())
    except Exception as exc:
        raise MatchingEngineUnavailable(f"Batch matching failed: {exc}") from exc
    created = []
    for proposal in result.trips:
        trip = apply_proposed_trip(db, proposal)
        created.append(str(trip.id))
    # Enqueue unmatched into priority queue
    now = _tz_now()
    for u in result.unmatched:
        g = db.query(Guest).filter(Guest.id == u.guest_id).first()
        if not g or not g.pickup_location_id or not g.accommodation_id:
            continue
        get_match_queue().enqueue(
            QueueItem(
                request_id=str(u.guest_id),
                guest_id=u.guest_id,
                party_size=g.party_size,
                luggage_count=g.luggage_count,
                origin_location_id=g.pickup_location_id,
                dest_location_id=g.accommodation_id,
                wait_started_at=now,
                deadline_at=(g.travel_eta + timedelta(minutes=45)) if g.travel_eta else None,
                priority=g.priority,
            ),
            now=now,
        )
    q = get_match_queue()
    return {
        "trips_created": len(created),
        "trip_ids": created,
        "unmatched": [{"guest_id": str(u.guest_id), "reason": u.reason.value, "detail": u.detail} for u in result.unmatched],
        "queue_depth": len(q),
    }


def enqueue_ride_request(
    db: Session,
    *,
    request_id: str,
    guest_id: UUID,
    wait_started_at: datetime | None = None,
) -> dict:
    g = db.query(Guest).filter(Guest.id == guest_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")
    if not g.pickup_location_id or not g.accommodation_id:
        raise HTTPException(status_code=400, detail="Guest missing locations")
    now = _tz_now()
    item = QueueItem(
        request_id=request_id,
        guest_id=guest_id,
        party_size=g.party_size,
        luggage_count=g.luggage_count,
        origin_location_id=g.pickup_location_id,
        dest_location_id=g.accommodation_id,
        wait_started_at=wait_started_at or now,
        deadline_at=(g.travel_eta + timedelta(minutes=45)) if g.travel_eta else None,
        priority=g.priority,
    )
    q = get_match_queue()
    q.enqueue(item, now=now)
    return {"queued": True, "request_id": request_id, "score": item.score, "queue_depth": len(q)}


def process_queue_once(db: Session) -> dict:
    now = _tz_now()
    q = get_match_queue()
    item = q.pop_next(now=now)
    if item is None:
        return {"processed": False, "reason": "empty"}
    try:
        trips = match_guest(db, item.guest_id)
        return {"processed": True, "guest_id": str(item.guest_id), "trips": [str(t.id) for t in trips]}
    except HTTPException as exc:
        # Requeue on failure so guest is not dropped
        q.requeue(item, now=now)
        return {"processed": False, "guest_id": str(item.guest_id), "reason": exc.detail, "requeued": True}
