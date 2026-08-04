"""Guest-role API — every query scoped to AuthContext.guest_id."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_guest
from app.db import get_db
from app.schemas import (
    GuestLocationRead,
    GuestMatchView,
    GuestMeRead,
    GuestRideRequestCreate,
    RideRequestRead,
)
from app.services import guest_ops_service

router = APIRouter(prefix="/guest", tags=["guest"])


def _guest_id(auth: AuthContext) -> UUID:
    assert auth.guest_id is not None
    return auth.guest_id


@router.get("/me", response_model=GuestMeRead)
def me(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_guest),
) -> GuestMeRead:
    return guest_ops_service.get_me(db, _guest_id(auth))


@router.get("/locations", response_model=list[GuestLocationRead])
def locations(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_guest),
) -> list[GuestLocationRead]:
    _ = auth  # auth gate only — locations are event-scoped public to guests
    return guest_ops_service.list_locations(db)


@router.get("/match", response_model=GuestMatchView | None)
def match(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_guest),
) -> GuestMatchView | None:
    """Returns null when the guest has no active trip (including after drop-off)."""
    return guest_ops_service.get_match(db, _guest_id(auth))


@router.get("/ride-requests", response_model=list[RideRequestRead])
def my_requests(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_guest),
) -> list[RideRequestRead]:
    return guest_ops_service.list_my_ride_requests(db, _guest_id(auth))


@router.post("/ride-requests", response_model=RideRequestRead, status_code=201)
def request_ride(
    payload: GuestRideRequestCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_guest),
) -> RideRequestRead:
    return guest_ops_service.create_ride_request(db, _guest_id(auth), payload)
