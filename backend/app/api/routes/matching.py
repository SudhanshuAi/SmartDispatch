from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin
from app.config import get_settings
from app.db import get_db
from app.redis_client import get_redis
from app.services import matching_service

router = APIRouter(prefix="/admin/matching", tags=["admin-matching"])


class EnqueueBody(BaseModel):
    guest_id: UUID
    request_id: str | None = None


@router.get("/status")
def matching_status(_: AuthContext = Depends(require_admin)) -> dict:
    """Health of matching stack — overrides and in-progress trips do not depend on this."""
    settings = get_settings()
    return {
        "matching_engine_enabled": settings.matching_engine_enabled,
        "redis": get_redis() is not None,
        "queue_backend": type(matching_service.get_match_queue()).__name__,
        "queue_depth": len(matching_service.get_match_queue()),
        "note": "When disabled/unavailable, in-progress trips and admin overrides still work.",
    }


@router.post("/batch")
def run_batch(
    limit: int | None = None,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    """Pre-day batch assignment via OR-Tools matching engine."""
    return matching_service.run_batch_assignment(db, limit=limit)


@router.post("/queue")
def enqueue(
    payload: EnqueueBody,
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    """Push an approved / unmatched request onto the priority queue."""
    rid = payload.request_id or str(payload.guest_id)
    return matching_service.enqueue_ride_request(db, request_id=rid, guest_id=payload.guest_id)


@router.post("/queue/process")
def process_queue(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    """Pop highest-priority queue item and run match_one."""
    return matching_service.process_queue_once(db)


@router.post("/queue/clear")
def clear_queue(_: AuthContext = Depends(require_admin)) -> dict:
    """Drop all queue entries (use after re-seed when Redis still has old guest IDs)."""
    return matching_service.clear_match_queue()
