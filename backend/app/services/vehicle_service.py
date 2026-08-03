from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Vehicle
from app.schemas import VehicleCreate, VehicleRead, VehicleUpdate


def list_vehicles(db: Session) -> list[VehicleRead]:
    return [VehicleRead.model_validate(v) for v in db.query(Vehicle).order_by(Vehicle.plate_number).all()]


def get_vehicle(db: Session, vehicle_id: UUID) -> VehicleRead:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return VehicleRead.model_validate(vehicle)


def create_vehicle(db: Session, payload: VehicleCreate) -> VehicleRead:
    if db.query(Vehicle).filter(Vehicle.plate_number == payload.plate_number).first():
        raise HTTPException(status_code=400, detail="Plate number already exists")
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


def update_vehicle(db: Session, vehicle_id: UUID, payload: VehicleUpdate) -> VehicleRead:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    data = payload.model_dump(exclude_unset=True)
    if "plate_number" in data:
        clash = (
            db.query(Vehicle)
            .filter(Vehicle.plate_number == data["plate_number"], Vehicle.id != vehicle_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=400, detail="Plate number already exists")
    for key, value in data.items():
        setattr(vehicle, key, value)
    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


def delete_vehicle(db: Session, vehicle_id: UUID) -> None:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.driver is not None:
        raise HTTPException(status_code=400, detail="Vehicle is assigned to a driver")
    db.delete(vehicle)
    db.commit()
