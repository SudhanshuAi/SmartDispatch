from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.db import get_db
from app.models.enums import RideRequestStatus
from app.schemas import (
    DashboardSnapshot,
    DriverOnboardRequest,
    DriverRead,
    ForceMatchRequest,
    GuestCreate,
    GuestRead,
    LocationRead,
    LoginRequest,
    MarkVehicleDownRequest,
    ReassignTripRequest,
    RideRequestCreate,
    RideRequestRead,
)
from app.services import ops_service

router = APIRouter(tags=["admin-ops"])


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """Stub login — returns role for Admin Portal RBAC routing."""
    return ops_service.stub_login(db, payload.email)


@router.get("/admin/locations", response_model=list[LocationRead])
def locations(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[LocationRead]:
    return ops_service.list_locations(db)


@router.get("/admin/dashboard", response_model=DashboardSnapshot)
def dashboard(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DashboardSnapshot:
    return ops_service.dashboard_snapshot(db)


@router.get("/admin/ride-requests", response_model=list[RideRequestRead])
def list_requests(
    status: RideRequestStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[RideRequestRead]:
    return ops_service.list_ride_requests(db, status)


@router.post("/admin/ride-requests", response_model=RideRequestRead, status_code=201)
def create_request(
    payload: RideRequestCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> RideRequestRead:
    return ops_service.create_ride_request(db, payload)


@router.post("/admin/ride-requests/seed-demo", response_model=list[RideRequestRead])
def seed_demo_requests(
    n: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> list[RideRequestRead]:
    return ops_service.seed_demo_ride_requests(db, n)


@router.post("/admin/ride-requests/{request_id}/approve")
def approve_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    return ops_service.approve_ride_request(db, request_id)


@router.post("/admin/ride-requests/{request_id}/decline", response_model=RideRequestRead)
def decline_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> RideRequestRead:
    return ops_service.decline_ride_request(db, request_id)


@router.post("/admin/drivers/onboard", response_model=DriverRead, status_code=201)
def onboard_driver(
    payload: DriverOnboardRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DriverRead:
    return ops_service.onboard_driver(db, payload)


@router.post("/admin/guests/walk-in", response_model=GuestRead, status_code=201)
def walk_in_guest(
    payload: GuestCreate,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> GuestRead:
    return ops_service.create_walk_in_guest(db, payload)


@router.post("/admin/override/reassign")
def override_reassign(
    payload: ReassignTripRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    return ops_service.reassign_trip(db, payload)


@router.post("/admin/override/vehicle-down", response_model=DriverRead)
def override_vehicle_down(
    payload: MarkVehicleDownRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> DriverRead:
    return ops_service.mark_vehicle_down(db, payload)


@router.post("/admin/override/force-match")
def override_force_match(
    payload: ForceMatchRequest,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    return ops_service.force_match(db, payload)
