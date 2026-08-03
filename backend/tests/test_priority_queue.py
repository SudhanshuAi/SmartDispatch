from datetime import timedelta

from app.matching_engine.priority_queue import InMemoryPriorityQueue, priority_score
from app.matching_engine.types import QueueItem
from uuid import uuid4


def test_aging_overtakes_capped_vip(now):
    vip_new = priority_score(
        wait_started_at=now,
        now=now,
        deadline_at=None,
        priority=True,
    )
    long_waiter = priority_score(
        wait_started_at=now - timedelta(minutes=40),
        now=now,
        deadline_at=None,
        priority=False,
    )
    assert long_waiter > vip_new


def test_queue_pop_order_prefers_aged(now):
    q = InMemoryPriorityQueue()
    vip = QueueItem(
        request_id="vip",
        guest_id=uuid4(),
        party_size=1,
        luggage_count=0,
        origin_location_id=uuid4(),
        dest_location_id=uuid4(),
        wait_started_at=now,
        priority=True,
    )
    aged = QueueItem(
        request_id="aged",
        guest_id=uuid4(),
        party_size=1,
        luggage_count=0,
        origin_location_id=uuid4(),
        dest_location_id=uuid4(),
        wait_started_at=now - timedelta(minutes=50),
        priority=False,
    )
    q.enqueue(vip, now=now)
    q.enqueue(aged, now=now)
    first = q.pop_next(now=now)
    assert first is not None
    assert first.request_id == "aged"


def test_requeue_preserves_wait_started(now):
    q = InMemoryPriorityQueue()
    item = QueueItem(
        request_id="r1",
        guest_id=uuid4(),
        party_size=1,
        luggage_count=0,
        origin_location_id=uuid4(),
        dest_location_id=uuid4(),
        wait_started_at=now - timedelta(minutes=20),
        priority=False,
    )
    q.enqueue(item, now=now)
    popped = q.pop_next(now=now)
    assert popped is not None
    later = now + timedelta(minutes=5)
    q.requeue(popped, now=later)
    again = q.pop_next(now=later)
    assert again is not None
    assert again.wait_started_at == now - timedelta(minutes=20)
