from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.db import get_db
from app.schemas import MatchGuestRequest, TripCreate, TripRead, TripUpdate
from app.services import trip_service

router = APIRouter(prefix="/admin/trips", tags=["admin-trips"])


@router.get("", response_model=list[TripRead])
def list_trips(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[TripRead]:
    return trip_service.list_trips(db)


@router.post("", response_model=TripRead, status_code=201)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> TripRead:
    return trip_service.create_trip(db, payload)


@router.post("/match", response_model=TripRead, status_code=201)
def match_guest(
    payload: MatchGuestRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> TripRead:
    """Delegate to MatchingEngine via service layer. No matching logic in this handler."""
    return trip_service.match_guest(db, payload)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> TripRead:
    return trip_service.get_trip(db, trip_id)


@router.patch("/{trip_id}", response_model=TripRead)
def update_trip(
    trip_id: UUID,
    payload: TripUpdate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> TripRead:
    return trip_service.update_trip(db, trip_id, payload)


@router.delete("/{trip_id}", status_code=204)
def delete_trip(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> None:
    trip_service.delete_trip(db, trip_id)
