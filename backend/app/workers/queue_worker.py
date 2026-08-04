"""Background priority-queue drain so waiting guests are not stuck until an admin clicks Process."""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)

QUEUE_POLL_SECONDS = 12
MAX_PER_TICK = 5


async def queue_drain_loop() -> None:
    while True:
        try:
            await asyncio.sleep(QUEUE_POLL_SECONDS)
            settings = get_settings()
            if not settings.matching_engine_enabled:
                continue
            from app.services import matching_service

            db = SessionLocal()
            try:
                for _ in range(MAX_PER_TICK):
                    result = matching_service.process_queue_once(db)
                    if not result.get("processed"):
                        break
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("queue_drain_loop tick failed")
