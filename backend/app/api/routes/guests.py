from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.db import get_db
from app.schemas import GuestCreate, GuestRead, GuestUpdate
from app.services import guest_service

router = APIRouter(prefix="/admin/guests", tags=["admin-guests"])


@router.get("", response_model=list[GuestRead])
def list_guests(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[GuestRead]:
    return guest_service.list_guests(db)


@router.get("/{guest_id}", response_model=GuestRead)
def get_guest(
    guest_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> GuestRead:
    return guest_service.get_guest(db, guest_id)


@router.post("", response_model=GuestRead, status_code=201)
def create_guest(
    payload: GuestCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> GuestRead:
    return guest_service.create_guest(db, payload)


@router.patch("/{guest_id}", response_model=GuestRead)
def update_guest(
    guest_id: UUID,
    payload: GuestUpdate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> GuestRead:
    return guest_service.update_guest(db, guest_id, payload)


@router.delete("/{guest_id}", status_code=204)
def delete_guest(
    guest_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> None:
    guest_service.delete_guest(db, guest_id)
