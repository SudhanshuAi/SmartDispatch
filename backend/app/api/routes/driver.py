"""Driver-role API — every query scoped to AuthContext.driver_id."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_driver
from app.db import get_db
from app.schemas import (
    DriverLocationUpdate,
    DriverMeRead,
    DriverRejectRequest,
    DriverTripStatusUpdate,
    DriverTripView,
)
from app.services import driver_ops_service

router = APIRouter(prefix="/driver", tags=["driver"])


def _driver_id(auth: AuthContext) -> UUID:
    assert auth.driver_id is not None
    return auth.driver_id


@router.get("/me", response_model=DriverMeRead)
def me(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> DriverMeRead:
    return driver_ops_service.get_me(db, _driver_id(auth))


@router.get("/trip", response_model=DriverTripView | None)
def current_trip(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> DriverTripView | None:
    return driver_ops_service.get_current_trip(db, _driver_id(auth))


@router.post("/trip/accept", response_model=DriverTripView)
def accept_trip(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> DriverTripView:
    return driver_ops_service.accept_trip(db, _driver_id(auth))


@router.post("/trip/reject")
def reject_trip(
    payload: DriverRejectRequest | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> dict:
    reason = payload.reason if payload else None
    return driver_ops_service.reject_trip(db, _driver_id(auth), reason=reason)


@router.post("/trip/status", response_model=DriverTripView)
def update_status(
    payload: DriverTripStatusUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> DriverTripView:
    return driver_ops_service.update_trip_status(db, _driver_id(auth), payload.action)


@router.post("/location")
def share_location(
    payload: DriverLocationUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> dict:
    return driver_ops_service.update_location(db, _driver_id(auth), payload)


@router.post("/break/end", response_model=DriverMeRead)
def end_break(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_driver),
) -> DriverMeRead:
    return driver_ops_service.end_break(db, _driver_id(auth))
