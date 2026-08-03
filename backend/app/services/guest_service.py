from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import Guest, Location, User
from app.models.enums import UserRole
from app.schemas import GuestCreate, GuestRead, GuestUpdate
from app.services.security import hash_password


def _to_read(guest: Guest) -> GuestRead:
    return GuestRead(
        id=guest.id,
        user_id=guest.user_id,
        party_size=guest.party_size,
        luggage_count=guest.luggage_count,
        travel_eta=guest.travel_eta,
        travel_mode=guest.travel_mode,
        travel_ref=guest.travel_ref,
        pickup_location_id=guest.pickup_location_id,
        accommodation_id=guest.accommodation_id,
        priority=guest.priority,
        attendance_status=guest.attendance_status,
        created_at=guest.created_at,
        email=guest.user.email if guest.user else None,
        full_name=guest.user.full_name if guest.user else None,
        phone=guest.user.phone if guest.user else None,
    )


def list_guests(db: Session) -> list[GuestRead]:
    rows = db.query(Guest).options(joinedload(Guest.user)).order_by(Guest.travel_eta).all()
    return [_to_read(g) for g in rows]


def get_guest(db: Session, guest_id: UUID) -> GuestRead:
    guest = db.query(Guest).options(joinedload(Guest.user)).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return _to_read(guest)


def create_guest(db: Session, payload: GuestCreate) -> GuestRead:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    for loc_id in (payload.pickup_location_id, payload.accommodation_id):
        if loc_id and not db.query(Location).filter(Location.id == loc_id).first():
            raise HTTPException(status_code=400, detail=f"Location {loc_id} not found")

    user = User(
        email=payload.email,
        role=UserRole.guest,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
    )
    db.add(user)
    db.flush()
    guest = Guest(
        user_id=user.id,
        party_size=payload.party_size,
        luggage_count=payload.luggage_count,
        travel_eta=payload.travel_eta,
        travel_mode=payload.travel_mode,
        travel_ref=payload.travel_ref,
        pickup_location_id=payload.pickup_location_id,
        accommodation_id=payload.accommodation_id,
        priority=payload.priority,
        attendance_status=payload.attendance_status,
    )
    db.add(guest)
    db.commit()
    return get_guest(db, guest.id)


def update_guest(db: Session, guest_id: UUID, payload: GuestUpdate) -> GuestRead:
    guest = db.query(Guest).options(joinedload(Guest.user)).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data:
        guest.user.full_name = data.pop("full_name")
    if "phone" in data:
        guest.user.phone = data.pop("phone")
    for key, value in data.items():
        setattr(guest, key, value)
    db.commit()
    return get_guest(db, guest_id)


def delete_guest(db: Session, guest_id: UUID) -> None:
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    user = guest.user
    db.delete(guest)
    if user:
        db.delete(user)
    db.commit()
