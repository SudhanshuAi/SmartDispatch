"""Priority score + sorted-set queue (Redis or in-memory for tests)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.matching_engine.types import QueueItem

# VIP boost capped so aging can overtake
VIP_BASE = 100.0
VIP_CAP = 150.0
WAIT_AGING_PER_MINUTE = 5.0
DEADLINE_URGENCY_PER_MINUTE = 2.0


def priority_score(
    *,
    wait_started_at: datetime,
    now: datetime,
    deadline_at: datetime | None,
    priority: bool,
) -> float:
    """Higher score = served sooner (Redis ZSET: we use negative for ZPOPMIN-friendly ascending)."""
    waited_min = max(0.0, (now - wait_started_at).total_seconds() / 60.0)
    base = min(VIP_BASE, VIP_CAP) if priority else 0.0
    aging = WAIT_AGING_PER_MINUTE * waited_min
    urgency = 0.0
    if deadline_at is not None:
        mins_to_deadline = (deadline_at - now).total_seconds() / 60.0
        if mins_to_deadline < 60:
            urgency = DEADLINE_URGENCY_PER_MINUTE * max(0.0, 60.0 - mins_to_deadline)
    return base + aging + urgency


def redis_zset_score(logical_score: float) -> float:
    """Redis ZPOPMIN pops lowest score first — invert so high priority pops first."""
    return -logical_score


class PriorityQueue(Protocol):
    def enqueue(self, item: QueueItem, *, now: datetime) -> None: ...

    def pop_next(self, *, now: datetime) -> QueueItem | None: ...

    def peek_scores(self, *, now: datetime) -> list[tuple[str, float]]: ...

    def requeue(self, item: QueueItem, *, now: datetime) -> None: ...

    def remove(self, request_id: str) -> None: ...

    def __len__(self) -> int: ...


@dataclass
class InMemoryPriorityQueue:
    """Test/dev stand-in with the same semantics as a Redis sorted set."""

    _items: dict[str, QueueItem] = None  # type: ignore[assignment]
    _scores: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._items is None:
            self._items = {}
        if self._scores is None:
            self._scores = {}

    def enqueue(self, item: QueueItem, *, now: datetime) -> None:
        score = priority_score(
            wait_started_at=item.wait_started_at,
            now=now,
            deadline_at=item.deadline_at,
            priority=item.priority,
        )
        item.score = score
        self._items[item.request_id] = item
        self._scores[item.request_id] = redis_zset_score(score)

    def requeue(self, item: QueueItem, *, now: datetime) -> None:
        self.enqueue(item, now=now)

    def pop_next(self, *, now: datetime) -> QueueItem | None:
        if not self._scores:
            return None
        # Refresh aging scores before pop
        for rid, item in list(self._items.items()):
            s = priority_score(
                wait_started_at=item.wait_started_at,
                now=now,
                deadline_at=item.deadline_at,
                priority=item.priority,
            )
            item.score = s
            self._scores[rid] = redis_zset_score(s)
        rid = min(self._scores, key=self._scores.get)  # type: ignore[arg-type]
        self._scores.pop(rid)
        return self._items.pop(rid)

    def peek_scores(self, *, now: datetime) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for rid, item in self._items.items():
            s = priority_score(
                wait_started_at=item.wait_started_at,
                now=now,
                deadline_at=item.deadline_at,
                priority=item.priority,
            )
            out.append((rid, s))
        out.sort(key=lambda x: -x[1])
        return out

    def remove(self, request_id: str) -> None:
        self._items.pop(request_id, None)
        self._scores.pop(request_id, None)

    def __len__(self) -> int:
        return len(self._items)


class RedisPriorityQueue:
    """Redis sorted-set backed queue — sole production queue per PLAN."""

    KEY = "smartdispatch:match_queue"

    def __init__(self, redis_client) -> None:  # noqa: ANN001
        self._r = redis_client
        self._payloads: dict[str, QueueItem] = {}

    def enqueue(self, item: QueueItem, *, now: datetime) -> None:
        score = priority_score(
            wait_started_at=item.wait_started_at,
            now=now,
            deadline_at=item.deadline_at,
            priority=item.priority,
        )
        item.score = score
        self._payloads[item.request_id] = item
        self._r.hset(f"{self.KEY}:payload", item.request_id, _serialize(item))
        self._r.zadd(self.KEY, {item.request_id: redis_zset_score(score)})

    def requeue(self, item: QueueItem, *, now: datetime) -> None:
        self.enqueue(item, now=now)

    def pop_next(self, *, now: datetime) -> QueueItem | None:
        # Refresh all scores for aging (bounded set at our scale)
        raw = self._r.zrange(self.KEY, 0, -1)
        if not raw:
            return None
        for rid in raw:
            rid_s = rid.decode() if isinstance(rid, bytes) else rid
            item = self._load(rid_s)
            if item is None:
                self._r.zrem(self.KEY, rid_s)
                continue
            s = priority_score(
                wait_started_at=item.wait_started_at,
                now=now,
                deadline_at=item.deadline_at,
                priority=item.priority,
            )
            item.score = s
            self._r.zadd(self.KEY, {rid_s: redis_zset_score(s)})
        popped = self._r.zpopmin(self.KEY, count=1)
        if not popped:
            return None
        rid, _ = popped[0]
        rid_s = rid.decode() if isinstance(rid, bytes) else rid
        item = self._load(rid_s)
        self._r.hdel(f"{self.KEY}:payload", rid_s)
        return item

    def peek_scores(self, *, now: datetime) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for rid in self._r.zrange(self.KEY, 0, -1):
            rid_s = rid.decode() if isinstance(rid, bytes) else rid
            item = self._load(rid_s)
            if item:
                s = priority_score(
                    wait_started_at=item.wait_started_at,
                    now=now,
                    deadline_at=item.deadline_at,
                    priority=item.priority,
                )
                out.append((rid_s, s))
        out.sort(key=lambda x: -x[1])
        return out

    def remove(self, request_id: str) -> None:
        self._r.zrem(self.KEY, request_id)
        self._r.hdel(f"{self.KEY}:payload", request_id)

    def __len__(self) -> int:
        return int(self._r.zcard(self.KEY))

    def _load(self, request_id: str) -> QueueItem | None:
        if request_id in self._payloads:
            return self._payloads[request_id]
        raw = self._r.hget(f"{self.KEY}:payload", request_id)
        if not raw:
            return None
        item = _deserialize(raw.decode() if isinstance(raw, bytes) else raw)
        self._payloads[request_id] = item
        return item


def _serialize(item: QueueItem) -> str:
    import json

    return json.dumps(
        {
            "request_id": item.request_id,
            "guest_id": str(item.guest_id),
            "party_size": item.party_size,
            "luggage_count": item.luggage_count,
            "origin_location_id": str(item.origin_location_id),
            "dest_location_id": str(item.dest_location_id),
            "wait_started_at": item.wait_started_at.isoformat(),
            "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
            "priority": item.priority,
            "score": item.score,
        }
    )


def _deserialize(raw: str) -> QueueItem:
    import json
    from datetime import datetime
    from uuid import UUID

    d = json.loads(raw)
    return QueueItem(
        request_id=d["request_id"],
        guest_id=UUID(d["guest_id"]),
        party_size=d["party_size"],
        luggage_count=d["luggage_count"],
        origin_location_id=UUID(d["origin_location_id"]),
        dest_location_id=UUID(d["dest_location_id"]),
        wait_started_at=datetime.fromisoformat(d["wait_started_at"]),
        deadline_at=datetime.fromisoformat(d["deadline_at"]) if d["deadline_at"] else None,
        priority=d["priority"],
        score=d.get("score", 0.0),
    )
