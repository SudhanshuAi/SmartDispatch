"""Capacity checks, split-group partitioning, fleet escalation."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

from app.matching_engine.types import DriverSnapshot, GuestSnapshot, UnmatchedGuest, UnmatchedReason


def fits_vehicle(guest: GuestSnapshot, seats: int, luggage: int) -> bool:
    return guest.party_size <= seats and guest.luggage_count <= luggage


def remaining_capacity(driver: DriverSnapshot) -> tuple[int, int]:
    used_seats = driver.current_trip.seats_used if driver.current_trip else 0
    used_lug = driver.current_trip.luggage_used if driver.current_trip else 0
    return driver.seat_capacity - used_seats, driver.luggage_capacity - used_lug


def can_accept(driver: DriverSnapshot, seats_needed: int, luggage_needed: int) -> bool:
    rem_s, rem_l = remaining_capacity(driver)
    return rem_s >= seats_needed and rem_l >= luggage_needed


def max_vehicle_capacity(drivers: list[DriverSnapshot]) -> tuple[int, int]:
    if not drivers:
        return 0, 0
    return max(d.seat_capacity for d in drivers), max(d.luggage_capacity for d in drivers)


def needs_split(guest: GuestSnapshot, drivers: list[DriverSnapshot]) -> bool:
    max_seats, max_lug = max_vehicle_capacity(drivers)
    return guest.party_size > max_seats or guest.luggage_count > max_lug


def split_party(
    guest: GuestSnapshot,
    drivers: list[DriverSnapshot],
    *,
    party_group_id: UUID | None = None,
) -> tuple[list[GuestSnapshot], UnmatchedGuest | None]:
    """
    Partition a large party into sub-groups that each fit the largest available vehicle.
    Seat total is preserved exactly; leftover luggage is packed into chunks with spare
    luggage capacity, then into additional min-seat chunks only if unavoidable.
    """
    max_seats, max_lug = max_vehicle_capacity(drivers)
    if max_seats <= 0:
        return [], UnmatchedGuest(guest.guest_id, UnmatchedReason.no_capacity, "no vehicles")

    if not needs_split(guest, drivers):
        return [guest], None

    group_id = party_group_id or uuid4()
    remaining_seats = guest.party_size
    remaining_lug = guest.luggage_count
    splits: list[GuestSnapshot] = []
    idx = 0

    while remaining_seats > 0:
        take_seats = min(remaining_seats, max_seats)
        take_lug = min(remaining_lug, max_lug)
        splits.append(
            GuestSnapshot(
                guest_id=guest.guest_id,
                party_size=take_seats,
                luggage_count=take_lug,
                pickup_location_id=guest.pickup_location_id,
                drop_location_id=guest.drop_location_id,
                ready_at=guest.ready_at,
                deadline_at=guest.deadline_at,
                priority=guest.priority,
                party_group_id=group_id,
                split_index=idx,
            )
        )
        remaining_seats -= take_seats
        remaining_lug -= take_lug
        idx += 1
        if idx > 50:
            return splits, UnmatchedGuest(
                guest.guest_id, UnmatchedReason.needs_escalation, "split exploded"
            )

    # Pack leftover luggage into existing chunks that still have room
    for i, s in enumerate(splits):
        if remaining_lug <= 0:
            break
        room = max_lug - s.luggage_count
        if room <= 0:
            continue
        add = min(room, remaining_lug)
        splits[i] = replace(s, luggage_count=s.luggage_count + add)
        remaining_lug -= add

    # Only if luggage still remains, open luggage-only chunks (1 seat each)
    while remaining_lug > 0:
        take_lug = min(remaining_lug, max_lug)
        splits.append(
            GuestSnapshot(
                guest_id=guest.guest_id,
                party_size=1,
                luggage_count=take_lug,
                pickup_location_id=guest.pickup_location_id,
                drop_location_id=guest.drop_location_id,
                ready_at=guest.ready_at,
                deadline_at=guest.deadline_at,
                priority=guest.priority,
                party_group_id=group_id,
                split_index=idx,
            )
        )
        remaining_lug -= take_lug
        idx += 1

    return splits, None


def fleet_can_cover(guests: list[GuestSnapshot], drivers: list[DriverSnapshot]) -> bool:
    total_seats = sum(g.party_size for g in guests)
    total_lug = sum(g.luggage_count for g in guests)
    fleet_seats = sum(d.seat_capacity for d in drivers)
    fleet_lug = sum(d.luggage_capacity for d in drivers)
    return total_seats <= fleet_seats and total_lug <= fleet_lug


def prepare_guests_for_matching(
    guests: list[GuestSnapshot],
    drivers: list[DriverSnapshot],
) -> tuple[list[GuestSnapshot], list[UnmatchedGuest], list[GuestSnapshot]]:
    """
    Expand oversized parties into splits; escalate when fleet cannot cover.
    Returns (matchable_guests, unmatched, all_split_records).
    """
    matchable: list[GuestSnapshot] = []
    unmatched: list[UnmatchedGuest] = []
    split_records: list[GuestSnapshot] = []

    for guest in guests:
        if needs_split(guest, drivers):
            splits, err = split_party(guest, drivers)
            if err and not splits:
                unmatched.append(err)
                continue
            if not fleet_can_cover(splits, drivers):
                unmatched.append(
                    UnmatchedGuest(
                        guest.guest_id,
                        UnmatchedReason.needs_escalation,
                        "party exceeds available fleet capacity",
                    )
                )
                continue
            split_records.extend(splits)
            matchable.extend(splits)
        else:
            matchable.append(guest)

    return matchable, unmatched, split_records
