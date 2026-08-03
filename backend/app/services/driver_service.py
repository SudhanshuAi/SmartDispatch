from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models import Driver, User, Vehicle
from app.models.enums import UserRole
from app.schemas import DriverCreate, DriverRead, DriverUpdate, VehicleRead
from app.services.security import hash_password


def _to_read(driver: Driver) -> DriverRead:
    return DriverRead(
        id=driver.id,
        user_id=driver.user_id,
        vehicle_id=driver.vehicle_id,
        status=driver.status,
        break_until=driver.break_until,
        predicted_free_at=driver.predicted_free_at,
        predicted_free_lat=driver.predicted_free_lat,
        predicted_free_lng=driver.predicted_free_lng,
        last_lat=driver.last_lat,
        last_lng=driver.last_lng,
        created_at=driver.created_at,
        email=driver.user.email if driver.user else None,
        full_name=driver.user.full_name if driver.user else None,
        phone=driver.user.phone if driver.user else None,
        vehicle=VehicleRead.model_validate(driver.vehicle) if driver.vehicle else None,
    )


def list_drivers(db: Session) -> list[DriverRead]:
    rows = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .order_by(Driver.created_at)
        .all()
    )
    return [_to_read(d) for d in rows]


def get_driver(db: Session, driver_id: UUID) -> DriverRead:
    driver = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .filter(Driver.id == driver_id)
        .first()
    )
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    return _to_read(driver)


def create_driver(db: Session, payload: DriverCreate) -> DriverRead:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    vehicle = db.query(Vehicle).filter(Vehicle.id == payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=400, detail="Vehicle not found")
    if vehicle.driver is not None:
        raise HTTPException(status_code=400, detail="Vehicle already assigned to a driver")

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
        vehicle_id=payload.vehicle_id,
        status=payload.status,
        last_lat=payload.last_lat,
        last_lng=payload.last_lng,
    )
    db.add(driver)
    db.commit()
    return get_driver(db, driver.id)


def update_driver(db: Session, driver_id: UUID, payload: DriverUpdate) -> DriverRead:
    driver = (
        db.query(Driver)
        .options(joinedload(Driver.user), joinedload(Driver.vehicle))
        .filter(Driver.id == driver_id)
        .first()
    )
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data:
        driver.user.full_name = data.pop("full_name")
    if "phone" in data:
        driver.user.phone = data.pop("phone")
    if "vehicle_id" in data:
        new_vid = data.pop("vehicle_id")
        vehicle = db.query(Vehicle).filter(Vehicle.id == new_vid).first()
        if not vehicle:
            raise HTTPException(status_code=400, detail="Vehicle not found")
        if vehicle.driver is not None and vehicle.driver.id != driver.id:
            raise HTTPException(status_code=400, detail="Vehicle already assigned")
        driver.vehicle_id = new_vid
    for key, value in data.items():
        setattr(driver, key, value)
    db.commit()
    return get_driver(db, driver_id)


def delete_driver(db: Session, driver_id: UUID) -> None:
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    user = driver.user
    db.delete(driver)
    if user:
        db.delete(user)
    db.commit()
