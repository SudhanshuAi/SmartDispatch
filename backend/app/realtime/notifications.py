"""Push notifications (Expo) + event log. Degrades to log/WS when no token."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from app.realtime.location_store import get_push_token
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

NOTIF_LOG = "smartdispatch:notifications"
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def notify(
    *,
    kind: str,
    title: str,
    body: str,
    audience: list[tuple[str, UUID]],  # (role, subject_id) role in guest|driver|admin
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Record + attempt Expo push for each audience member with a registered token.
    Always returns a summary for tests / admin visibility.
    """
    data = data or {}
    event = {"kind": kind, "title": title, "body": body, "data": data, "audience": []}
    tokens: list[str] = []
    for role, sid in audience:
        event["audience"].append({"role": role, "id": str(sid)})
        tok = get_push_token(role, sid)
        if tok:
            tokens.append(tok)

    r = get_redis()
    if r is not None:
        import json

        r.lpush(NOTIF_LOG, json.dumps(event))
        r.ltrim(NOTIF_LOG, 0, 499)

    pushed = 0
    if tokens:
        messages = [
            {"to": t, "title": title, "body": body, "data": {"kind": kind, **data}, "sound": "default"}
            for t in tokens
        ]
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(EXPO_PUSH_URL, json=messages)
                if res.status_code < 300:
                    pushed = len(messages)
                else:
                    logger.warning("Expo push HTTP %s: %s", res.status_code, res.text[:200])
        except Exception as exc:
            logger.warning("Expo push failed: %s", exc)

    logger.info("notify kind=%s audience=%s pushed=%s", kind, len(audience), pushed)
    return {"kind": kind, "logged": True, "pushed": pushed, "event": event}


def recent_notifications(limit: int = 50) -> list[dict]:
    r = get_redis()
    if r is None:
        return []
    import json

    rows = r.lrange(NOTIF_LOG, 0, limit - 1) or []
    out = []
    for raw in rows:
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out
