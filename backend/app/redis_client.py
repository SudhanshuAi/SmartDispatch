"""Redis connection — optional; app degrades to in-memory when Redis is down."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Any | None = None
_unavailable = False


def get_redis():
    """Return a live Redis client or None if unavailable."""
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        try:
            _client.ping()
            return _client
        except Exception:
            _client = None
    try:
        import redis

        settings = get_settings()
        c = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.5)
        c.ping()
        _client = c
        return _client
    except Exception as exc:
        logger.warning("Redis unavailable (%s); using in-memory fallbacks", exc)
        _unavailable = True
        return None


def reset_redis_state_for_tests() -> None:
    global _client, _unavailable
    _client = None
    _unavailable = False
