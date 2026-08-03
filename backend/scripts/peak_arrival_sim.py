#!/usr/bin/env python
"""
Peak-arrival simulation against the Matching Engine (M7).

Scale: tens–hundreds of drivers, few hundred guests, burst window.
Reports: avg wait, unmatched/starved, capacity violations, match_one latency.

Usage (from backend/ with venv):
  python -m scripts.peak_arrival_sim
  python -m scripts.peak_arrival_sim --drivers 80 --guests 250 --window-min 20
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.constants import MATCH_ONE_P95_MS
from app.matching_engine.engine import DispatchMatchingEngine
from app.matching_engine.routing import CachedTravelProvider
from app.matching_engine.types import (
    ActiveTripSnapshot,
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    ProposedTrip,
    StopSnapshot,
)


@dataclass
class SimMetrics:
    latencies_ms: list[float] = field(default_factory=list)
    waits_min: list[float] = field(default_factory=list)
    unmatched: list[tuple[str, str]] = field(default_factory=list)
    capacity_violations: list[str] = field(default_factory=list)
    matched: int = 0
    detours: int = 0
    split_trips: int = 0
    matrix_calls: int = 0
    cache_hits: int = 0


def _fleet(n_drivers: int, *, seats: int = 4, luggage: int = 3) -> list[DriverSnapshot]:
    drivers: list[DriverSnapshot] = []
    for i in range(n_drivers):
        s = 6 if i % 5 == 0 else (7 if i % 11 == 0 else seats)
        lug = 5 if i % 5 == 0 else luggage
        lat = 28.5562 + (i % 20) * 0.003
        lng = 77.1000 + (i % 15) * 0.004
        drivers.append(
            DriverSnapshot(
                driver_id=uuid4(),
                vehicle_id=uuid4(),
                seat_capacity=s,
                luggage_capacity=lug,
                status="available",
                break_until=None,
                live_position=GeoPoint(lat, lng),
                predicted_free_at=None,
                predicted_free_position=None,
                depot=GeoPoint(lat, lng),
                current_trip=None,
            )
        )
    return drivers


def _locations(n_hotels: int = 8) -> dict:
    airport = uuid4()
    station = uuid4()
    hotels = [uuid4() for _ in range(n_hotels)]
    loc_map: dict[UUID, GeoPoint] = {
        airport: GeoPoint(28.5562, 77.1000),
        station: GeoPoint(28.6430, 77.2190),
    }
    for i, hid in enumerate(hotels):
        loc_map[hid] = GeoPoint(28.6000 + i * 0.008, 77.2000 + (i % 4) * 0.01)
    return {"airport": airport, "station": station, "hotels": hotels, "map": loc_map}


def _guests(n: int, locs, *, window_min: int, now: datetime) -> list[GuestSnapshot]:
    guests: list[GuestSnapshot] = []
    peak_n = int(n * 0.7)
    for i in range(n):
        if i < peak_n:
            offset = (i / max(1, peak_n)) * (window_min * 0.4)
        else:
            offset = (window_min * 0.4) + ((i - peak_n) / max(1, n - peak_n)) * (window_min * 0.6)
        ready = now + timedelta(minutes=offset)
        pickup = locs["airport"] if i % 5 != 0 else locs["station"]
        drop = locs["hotels"][i % len(locs["hotels"])]
        party = 1 if i % 7 else (3 if i % 11 else (5 if i % 23 == 0 else 2))
        if i % 41 == 0:
            party = 9
        lug = min(party, 4) if party < 9 else 6
        guests.append(
            GuestSnapshot(
                guest_id=uuid4(),
                party_size=party,
                luggage_count=lug,
                pickup_location_id=pickup,
                drop_location_id=drop,
                ready_at=ready,
                deadline_at=ready + timedelta(minutes=50),
                priority=(i % 20 == 0),
            )
        )
    guests.sort(key=lambda g: g.ready_at)
    return guests


def _stops_from_proposal(proposal: ProposedTrip, loc_map: dict[UUID, GeoPoint]) -> tuple[StopSnapshot, ...]:
    out = []
    for ps in proposal.stops:
        pt = loc_map.get(ps.location_id, GeoPoint(28.6, 77.2))
        out.append(
            StopSnapshot(
                ps.location_id,
                pt.lat,
                pt.lng,
                ps.stop_type,
                ps.guest_id,
                ps.sequence,
                ps.deadline_at,
            )
        )
    return tuple(out)


def _apply_to_fleet(
    drivers: list[DriverSnapshot],
    proposal: ProposedTrip,
    loc_map: dict[UUID, GeoPoint],
) -> None:
    idx = next(i for i, d in enumerate(drivers) if d.driver_id == proposal.driver_id)
    d = drivers[idx]
    trip_id = proposal.existing_trip_id or uuid4()
    version = (d.current_trip.route_version + 1) if d.current_trip else 1
    drivers[idx] = DriverSnapshot(
        driver_id=d.driver_id,
        vehicle_id=d.vehicle_id,
        seat_capacity=d.seat_capacity,
        luggage_capacity=d.luggage_capacity,
        status="en_route" if not d.current_trip else d.status,
        break_until=d.break_until,
        live_position=d.live_position,
        predicted_free_at=proposal.eta_drop,
        predicted_free_position=None,
        depot=d.depot,
        current_trip=ActiveTripSnapshot(
            trip_id=trip_id,
            route_version=version,
            seats_used=proposal.seats_used,
            luggage_used=proposal.luggage_used,
            trip_type=proposal.trip_type,
            stops=_stops_from_proposal(proposal, loc_map),
        ),
    )


def _check_capacity(drivers: list[DriverSnapshot], proposal: ProposedTrip, metrics: SimMetrics) -> None:
    d = next(x for x in drivers if x.driver_id == proposal.driver_id)
    if proposal.seats_used > d.seat_capacity or proposal.luggage_used > d.luggage_capacity:
        metrics.capacity_violations.append(
            f"driver={d.driver_id} seats={proposal.seats_used}/{d.seat_capacity} "
            f"lug={proposal.luggage_used}/{d.luggage_capacity}"
        )


def _free_drivers(drivers: list[DriverSnapshot], *, now: datetime) -> None:
    """Return drivers to available when their predicted free time has passed."""
    for i, d in enumerate(drivers):
        if d.predicted_free_at is not None and d.predicted_free_at <= now:
            drivers[i] = DriverSnapshot(
                driver_id=d.driver_id,
                vehicle_id=d.vehicle_id,
                seat_capacity=d.seat_capacity,
                luggage_capacity=d.luggage_capacity,
                status="available",
                break_until=None,
                live_position=d.predicted_free_position or d.live_position,
                predicted_free_at=None,
                predicted_free_position=None,
                depot=d.depot,
                current_trip=None,
            )
        elif d.status == "en_route" and d.current_trip and d.predicted_free_at is None:
            # No ETA — leave as-is
            pass


def run_sim(*, n_drivers: int = 80, n_guests: int = 250, window_min: int = 25) -> SimMetrics:
    now = datetime(2026, 8, 7, 8, 0, tzinfo=timezone.utc)
    locs = _locations()
    drivers = _fleet(n_drivers)
    guests = _guests(n_guests, locs, window_min=window_min, now=now)
    travel = CachedTravelProvider(traffic_mode=True)
    engine = DispatchMatchingEngine(travel=travel)
    metrics = SimMetrics()
    loc_map = locs["map"]

    for g in guests:
        _free_drivers(drivers, now=g.ready_at)
        t0 = time.perf_counter()
        result = engine.match_one(g, drivers, loc_map, now=g.ready_at)
        metrics.latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        if not result.matched:
            reason = result.unmatched.reason.value if result.unmatched else "unknown"
            metrics.unmatched.append((str(g.guest_id), reason))
            continue

        trips = result.all_trips()
        if len(trips) > 1:
            metrics.split_trips += 1
        for proposal in trips:
            _check_capacity(drivers, proposal, metrics)
            if proposal.source == "detour":
                metrics.detours += 1
            if proposal.eta_pickup:
                wait = max(0.0, (proposal.eta_pickup - g.ready_at).total_seconds() / 60.0)
                metrics.waits_min.append(wait)
            _apply_to_fleet(drivers, proposal, loc_map)
            metrics.matched += 1

    metrics.matrix_calls = travel.matrix_calls
    metrics.cache_hits = travel.cache_hits
    return metrics


def _count_reasons(rows: list[tuple[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for _, reason in rows:
        out[reason] = out.get(reason, 0) + 1
    return out


def report(metrics: SimMetrics, *, n_guests: int) -> dict:
    waits = metrics.waits_min
    lats = metrics.latencies_ms
    p95 = sorted(lats)[int(0.95 * (len(lats) - 1))] if lats else 0.0
    avg_wait = statistics.mean(waits) if waits else None
    starved = [u for u in metrics.unmatched if u[1] in {"no_feasible_driver", "deadline_miss"}]
    return {
        "guests": n_guests,
        "matched_assignments": metrics.matched,
        "unmatched_guests": len(metrics.unmatched),
        "starved_guests": len(starved),
        "unmatched_breakdown": _count_reasons(metrics.unmatched),
        "avg_wait_minutes": round(avg_wait, 2) if avg_wait is not None else None,
        "p95_wait_minutes": round(sorted(waits)[int(0.95 * (len(waits) - 1))], 2) if waits else None,
        "capacity_violations": len(metrics.capacity_violations),
        "capacity_violation_samples": metrics.capacity_violations[:5],
        "detours": metrics.detours,
        "split_groups": metrics.split_trips,
        "match_one_latency_ms": {
            "avg": round(statistics.mean(lats), 2) if lats else None,
            "p50": round(statistics.median(lats), 2) if lats else None,
            "p95": round(p95, 2),
            "max": round(max(lats), 2) if lats else None,
            "budget_p95_ms": MATCH_ONE_P95_MS,
            "p95_ok": p95 <= MATCH_ONE_P95_MS,
        },
        "routing": {"matrix_calls": metrics.matrix_calls, "cache_hits": metrics.cache_hits},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Peak arrival matching simulation")
    parser.add_argument("--drivers", type=int, default=100)
    parser.add_argument("--guests", type=int, default=250)
    parser.add_argument("--window-min", type=int, default=25)
    args = parser.parse_args()

    print(
        f"Running peak arrival: {args.drivers} drivers, {args.guests} guests, "
        f"{args.window_min} min window…"
    )
    metrics = run_sim(n_drivers=args.drivers, n_guests=args.guests, window_min=args.window_min)
    summary = report(metrics, n_guests=args.guests)
    print(json.dumps(summary, indent=2))

    assert summary["capacity_violations"] == 0, summary["capacity_violation_samples"]
    assert summary["match_one_latency_ms"]["p95_ok"], summary["match_one_latency_ms"]
    starve_rate = summary["starved_guests"] / max(1, args.guests)
    if starve_rate > 0.15:
        raise SystemExit(f"FAIL: starved rate {starve_rate:.1%} > 15%")
    print("\nOK — capacity clean, match_one p95 within budget, starvation within bounds.")


if __name__ == "__main__":
    main()
