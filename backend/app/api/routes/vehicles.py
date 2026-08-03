from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.db import get_db
from app.schemas import VehicleCreate, VehicleRead, VehicleUpdate
from app.services import vehicle_service

router = APIRouter(prefix="/admin/vehicles", tags=["admin-vehicles"])


@router.get("", response_model=list[VehicleRead])
def list_vehicles(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[VehicleRead]:
    return vehicle_service.list_vehicles(db)


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> VehicleRead:
    return vehicle_service.get_vehicle(db, vehicle_id)


@router.post("", response_model=VehicleRead, status_code=201)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> VehicleRead:
    return vehicle_service.create_vehicle(db, payload)


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> VehicleRead:
    return vehicle_service.update_vehicle(db, vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> None:
    vehicle_service.delete_vehicle(db, vehicle_id)
