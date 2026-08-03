"""In-process WebSocket hub + Redis pub/sub fan-out for live events."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

CHANNEL = "smartdispatch:realtime"


class RealtimeHub:
    def __init__(self) -> None:
        # channel -> set of websockets
        self._subs: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._listener_started = False

    async def connect(self, websocket: WebSocket, channels: list[str]) -> None:
        await websocket.accept()
        async with self._lock:
            for ch in channels:
                self._subs[ch].add(websocket)
        await self._ensure_listener()

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            for ch, socks in list(self._subs.items()):
                socks.discard(websocket)
                if not socks:
                    del self._subs[ch]

    async def publish(self, channels: list[str], event: dict[str, Any]) -> None:
        """Publish locally and via Redis so multi-worker can fan out."""
        payload = json.dumps({"channels": channels, "event": event})
        r = get_redis()
        if r is not None:
            try:
                r.publish(CHANNEL, payload)
            except Exception as exc:
                logger.debug("Redis publish failed: %s", exc)
        await self._broadcast(channels, event)

    async def _broadcast(self, channels: list[str], event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            targets: set[WebSocket] = set()
            for ch in channels:
                targets |= self._subs.get(ch, set())
            for ws in targets:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def _ensure_listener(self) -> None:
        if self._listener_started:
            return
        self._listener_started = True
        asyncio.create_task(self._redis_listen())

    async def _redis_listen(self) -> None:
        r = get_redis()
        if r is None:
            return
        try:
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(CHANNEL)
            while True:
                msg = await asyncio.to_thread(pubsub.get_message, True, 1.0)
                if not msg or msg.get("type") != "message":
                    await asyncio.sleep(0.05)
                    continue
                data = msg.get("data")
                if isinstance(data, bytes):
                    data = data.decode()
                try:
                    body = json.loads(data)
                    await self._broadcast(body["channels"], body["event"])
                except Exception as exc:
                    logger.debug("Bad pubsub payload: %s", exc)
        except Exception as exc:
            logger.warning("Realtime Redis listener stopped: %s", exc)
            self._listener_started = False


hub = RealtimeHub()


def channels_for_trip(*, trip_id: UUID, driver_id: UUID | None, guest_ids: list[UUID]) -> list[str]:
    ch = [f"trip:{trip_id}", "admin:ops"]
    if driver_id:
        ch.append(f"driver:{driver_id}")
    for gid in guest_ids:
        ch.append(f"guest:{gid}")
    return ch
