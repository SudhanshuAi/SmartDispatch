"""Pre-day batch assignment using OR-Tools CP-SAT."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from ortools.sat.python import cp_model

from app.constants import MANDATORY_BREAK_MINUTES
from app.matching_engine.capacity import prepare_guests_for_matching
from app.matching_engine.routing import CachedTravelProvider, TravelTimeProvider
from app.matching_engine.types import (
    BatchResult,
    DriverSnapshot,
    GeoPoint,
    GuestSnapshot,
    ProposedStop,
    ProposedTrip,
    UnmatchedGuest,
    UnmatchedReason,
)


def run_batch(
    guests: list[GuestSnapshot],
    drivers: list[DriverSnapshot],
    locations: dict[UUID, GeoPoint],
    *,
    now: datetime,
    travel: TravelTimeProvider | None = None,
    trip_type: str = "arrival",
    max_wait_minutes: int = 45,
    time_limit_seconds: float = 5.0,
) -> BatchResult:
    """
    Assign guests with known arrival times to drivers.
    Pure function — returns proposals only.
    """
    travel = travel or CachedTravelProvider(traffic_mode=False)
    assignable = [
        d
        for d in drivers
        if d.status in {"available", "offline"}  # offline still planned for pre-day; filtered by break
        or d.status == "available"
    ]
    # Pre-day: treat all non-disabled drivers as usable from depot
    assignable = [d for d in drivers if d.status != "on_break"]

    matchable, early_unmatched, splits = prepare_guests_for_matching(guests, assignable)
    if not matchable:
        return BatchResult(trips=(), unmatched=tuple(early_unmatched), splits=tuple(splits))

    if not assignable:
        unmatched = list(early_unmatched) + [
            UnmatchedGuest(g.guest_id, UnmatchedReason.no_feasible_driver, "no drivers") for g in matchable
        ]
        return BatchResult(trips=(), unmatched=tuple(unmatched), splits=tuple(splits))

    # Precompute costs / feasibility
    n_g, n_d = len(matchable), len(assignable)
    cost: list[list[int]] = [[0] * n_d for _ in range(n_g)]
    feasible: list[list[bool]] = [[False] * n_d for _ in range(n_g)]

    pairs: list[tuple[GeoPoint, GeoPoint]] = []
    pair_index: dict[tuple[int, int, str], int] = {}

    def _idx(o: GeoPoint, d: GeoPoint, tag: str, gi: int, di: int) -> None:
        pair_index[(gi, di, tag)] = len(pairs)
        pairs.append((o, d))

    for gi, g in enumerate(matchable):
        pickup = locations[g.pickup_location_id]
        drop = locations[g.drop_location_id]
        for di, drv in enumerate(assignable):
            start = drv.depot
            _idx(start, pickup, "to_pickup", gi, di)
            _idx(pickup, drop, "trip", gi, di)

    durs = travel.batch_durations(pairs, now=now)

    for gi, g in enumerate(matchable):
        for di, drv in enumerate(assignable):
            if g.party_size > drv.seat_capacity or g.luggage_count > drv.luggage_capacity:
                continue
            to_pickup = durs[pair_index[(gi, di, "to_pickup")]]
            trip_secs = durs[pair_index[(gi, di, "trip")]]
            start_time = now
            if drv.break_until and drv.break_until > now:
                start_time = drv.break_until
            pickup_eta = max(start_time + timedelta(seconds=to_pickup), g.ready_at)
            drop_eta = pickup_eta + timedelta(seconds=trip_secs)
            deadline = g.deadline_at or (g.ready_at + timedelta(minutes=max_wait_minutes))
            if drop_eta > deadline:
                continue
            wait = int((pickup_eta - g.ready_at).total_seconds())
            travel_cost = to_pickup + trip_secs
            vip = -200 if g.priority else 0
            cost[gi][di] = max(0, wait + travel_cost + vip)
            feasible[gi][di] = True

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for gi in range(n_g):
        for di in range(n_d):
            if feasible[gi][di]:
                x[gi, di] = model.NewBoolVar(f"x_{gi}_{di}")

    # Each guest at most one driver
    for gi in range(n_g):
        vars_g = [x[gi, di] for di in range(n_d) if (gi, di) in x]
        if vars_g:
            model.Add(sum(vars_g) <= 1)
        else:
            # no feasible driver encoded — leave unmatched
            pass

    # Capacity per driver
    for di, drv in enumerate(assignable):
        seat_terms = []
        lug_terms = []
        for gi, g in enumerate(matchable):
            if (gi, di) in x:
                seat_terms.append(x[gi, di] * g.party_size)
                lug_terms.append(x[gi, di] * g.luggage_count)
        if seat_terms:
            model.Add(sum(seat_terms) <= drv.seat_capacity)
            model.Add(sum(lug_terms) <= drv.luggage_capacity)

    # Objective: minimize cost + penalty for unassigned
    # Soft bonus: cluster same-destination guests onto the same vehicle
    SAME_DEST_BONUS = 180
    UNASSIGNED_PENALTY = 1_000_000
    obj_terms = []
    for gi in range(n_g):
        assigned = []
        for di in range(n_d):
            if (gi, di) in x:
                obj_terms.append(x[gi, di] * cost[gi][di])
                assigned.append(x[gi, di])
        if assigned:
            # 1 - sum(assigned) approx via penalty
            u = model.NewBoolVar(f"u_{gi}")
            model.Add(sum(assigned) + u == 1)
            obj_terms.append(u * UNASSIGNED_PENALTY)
        else:
            obj_terms.append(UNASSIGNED_PENALTY)

    for gi, g in enumerate(matchable):
        for gj in range(gi + 1, n_g):
            g2 = matchable[gj]
            if g.drop_location_id != g2.drop_location_id:
                continue
            for di in range(n_d):
                if (gi, di) not in x or (gj, di) not in x:
                    continue
                both = model.NewBoolVar(f"same_dest_{gi}_{gj}_{di}")
                model.AddBoolAnd([x[gi, di], x[gj, di]]).OnlyEnforceIf(both)
                model.AddBoolOr([x[gi, di].Not(), x[gj, di].Not(), both])
                obj_terms.append(both * -SAME_DEST_BONUS)

    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    trips: list[ProposedTrip] = []
    unmatched: list[UnmatchedGuest] = list(early_unmatched)
    assigned_guests: set[int] = set()

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Group guests by driver for shared-ride stop building
        by_driver: dict[int, list[int]] = {di: [] for di in range(n_d)}
        for gi in range(n_g):
            for di in range(n_d):
                if (gi, di) in x and solver.Value(x[gi, di]) == 1:
                    by_driver[di].append(gi)
                    assigned_guests.add(gi)

        for di, gis in by_driver.items():
            if not gis:
                continue
            drv = assignable[di]
            # Order by ready_at then pickup
            gis_sorted = sorted(gis, key=lambda i: (matchable[i].ready_at, matchable[i].guest_id.int))
            guests_d = [matchable[i] for i in gis_sorted]
            # Shared ride: same drop preferred; if mixed drops, still sequential
            stops: list[ProposedStop] = []
            seq = 0
            cursor_time = now
            if drv.break_until and drv.break_until > cursor_time:
                cursor_time = drv.break_until
            cursor_pos = drv.depot
            pickup_etas: list[datetime] = []
            for g in guests_d:
                pickup = locations[g.pickup_location_id]
                secs = travel.duration_seconds(cursor_pos, pickup, now=now)
                arrive = cursor_time + timedelta(seconds=secs)
                pickup_eta = max(arrive, g.ready_at)
                stops.append(
                    ProposedStop(g.pickup_location_id, "pickup", g.guest_id, seq, g.deadline_at, pickup_eta)
                )
                seq += 1
                pickup_etas.append(pickup_eta)
                cursor_time = pickup_eta
                cursor_pos = pickup
            # Drops in pickup order (or same dest once)
            drop_eta_last = cursor_time
            for g in guests_d:
                drop = locations[g.drop_location_id]
                secs = travel.duration_seconds(cursor_pos, drop, now=now)
                drop_eta = cursor_time + timedelta(seconds=secs)
                stops.append(
                    ProposedStop(g.drop_location_id, "drop", g.guest_id, seq, g.deadline_at, drop_eta)
                )
                seq += 1
                cursor_time = drop_eta + timedelta(minutes=0)
                cursor_pos = drop
                drop_eta_last = drop_eta

            seats = sum(g.party_size for g in guests_d)
            lug = sum(g.luggage_count for g in guests_d)
            party_group = next((g.party_group_id for g in guests_d if g.party_group_id), None)
            trips.append(
                ProposedTrip(
                    driver_id=drv.driver_id,
                    vehicle_id=drv.vehicle_id,
                    guest_ids=tuple(g.guest_id for g in guests_d),
                    origin_location_id=guests_d[0].pickup_location_id,
                    dest_location_id=guests_d[0].drop_location_id,
                    trip_type=trip_type,
                    seats_used=seats,
                    luggage_used=lug,
                    scheduled_pickup_at=guests_d[0].ready_at,
                    eta_pickup=pickup_etas[0] if pickup_etas else None,
                    eta_drop=drop_eta_last,
                    stops=tuple(stops),
                    party_group_id=party_group,
                    source="batch",
                    notes=f"break_after_min={MANDATORY_BREAK_MINUTES}",
                )
            )

    for gi, g in enumerate(matchable):
        if gi not in assigned_guests:
            # Find why
            any_cap = any(
                g.party_size <= d.seat_capacity and g.luggage_count <= d.luggage_capacity for d in assignable
            )
            reason = UnmatchedReason.no_capacity if not any_cap else UnmatchedReason.infeasible_eta
            if not any(feasible[gi][di] for di in range(n_d)):
                reason = UnmatchedReason.no_feasible_driver
            unmatched.append(UnmatchedGuest(g.guest_id, reason, "batch_unassigned"))

    return BatchResult(trips=tuple(trips), unmatched=tuple(unmatched), splits=tuple(splits))
