"""WebSocket realtime channels + push token registration + reopt trigger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_admin, require_driver, require_guest
from app.db import get_db
from app.realtime.hub import hub
from app.realtime.location_store import set_push_token
from app.realtime.notifications import recent_notifications
from app.realtime.reopt_service import apply_live_eta_reopt

router = APIRouter(tags=["realtime"])


class PushTokenBody(BaseModel):
    token: str


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query(...),
    subject_id: str | None = Query(default=None),
    trip_id: str | None = Query(default=None),
) -> None:
    """
    Subscribe to realtime channels.
      /ws?role=admin
      /ws?role=driver&subject_id=<driver_uuid>
      /ws?role=guest&subject_id=<guest_uuid>&trip_id=<trip_uuid>
    """
    channels: list[str] = []
    role = role.lower()
    if role == "admin":
        channels = ["admin:ops"]
    elif role == "driver":
        if not subject_id:
            await websocket.close(code=4401)
            return
        channels = [f"driver:{subject_id}"]
        if trip_id:
            channels.append(f"trip:{trip_id}")
    elif role == "guest":
        if not subject_id:
            await websocket.close(code=4401)
            return
        channels = [f"guest:{subject_id}"]
        if trip_id:
            channels.append(f"trip:{trip_id}")
    else:
        await websocket.close(code=4403)
        return

    await hub.connect(websocket, channels)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)


@router.post("/guest/push-token")
def guest_push_token(
    body: PushTokenBody,
    auth: AuthContext = Depends(require_guest),
) -> dict:
    assert auth.guest_id
    set_push_token("guest", auth.guest_id, body.token)
    return {"ok": True}


@router.post("/driver/push-token")
def driver_push_token(
    body: PushTokenBody,
    auth: AuthContext = Depends(require_driver),
) -> dict:
    assert auth.driver_id
    set_push_token("driver", auth.driver_id, body.token)
    return {"ok": True}


@router.post("/admin/realtime/reopt")
def trigger_reopt(
    db: Session = Depends(get_db),
    _: AuthContext = Depends(require_admin),
) -> dict:
    return apply_live_eta_reopt(db)


@router.get("/admin/realtime/notifications")
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    _: AuthContext = Depends(require_admin),
) -> list[dict]:
    return recent_notifications(limit)
