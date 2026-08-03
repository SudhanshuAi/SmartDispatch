from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.db import get_db
from app.schemas import DriverCreate, DriverRead, DriverUpdate
from app.services import driver_service

router = APIRouter(prefix="/admin/drivers", tags=["admin-drivers"])


@router.get("", response_model=list[DriverRead])
def list_drivers(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[DriverRead]:
    return driver_service.list_drivers(db)


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver(
    driver_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DriverRead:
    return driver_service.get_driver(db, driver_id)


@router.post("", response_model=DriverRead, status_code=201)
def create_driver(
    payload: DriverCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DriverRead:
    return driver_service.create_driver(db, payload)


@router.patch("/{driver_id}", response_model=DriverRead)
def update_driver(
    driver_id: UUID,
    payload: DriverUpdate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DriverRead:
    return driver_service.update_driver(db, driver_id, payload)


@router.delete("/{driver_id}", status_code=204)
def delete_driver(
    driver_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> None:
    driver_service.delete_driver(db, driver_id)
