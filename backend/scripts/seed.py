"""
Seed a realistic single-event dataset.

Creates:
  - 1 admin user
  - Locations: 1 airport, 1 station, 1 venue, 3 hotels
  - Event schedule phases
  - ~25 drivers with varying vehicle capacity
  - ~150 guests with staggered airport/station arrivals

Usage (from backend/):
  python -m scripts.seed
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow `python -m scripts.seed` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import (  # noqa: F401 — ensure metadata
    Driver,
    EventSchedule,
    Guest,
    Location,
    User,
    Vehicle,
)
from app.models.enums import (
    AttendanceStatus,
    DriverStatus,
    LocationType,
    TripType,
    UserRole,
)
from app.services.security import hash_password

# Approx downtown / airport / station coords (fictional metro area)
LOCATIONS = [
    {
        "name": "Metro International Airport (T1)",
        "type": LocationType.airport,
        "address": "1 Airport Blvd",
        "lat": 28.5562,
        "lng": 77.1000,
    },
    {
        "name": "Central Railway Station",
        "type": LocationType.station,
        "address": "Station Road",
        "lat": 28.6430,
        "lng": 77.2190,
    },
    {
        "name": "Grand Convention Venue",
        "type": LocationType.venue,
        "address": "100 Summit Way",
        "lat": 28.6139,
        "lng": 77.2090,
    },
    {
        "name": "Hotel Aurora",
        "type": LocationType.hotel,
        "address": "12 Aurora Lane",
        "lat": 28.6205,
        "lng": 77.2150,
    },
    {
        "name": "Hotel Meridian",
        "type": LocationType.hotel,
        "address": "45 Meridian Ave",
        "lat": 28.6080,
        "lng": 77.2250,
    },
    {
        "name": "Hotel Cascade",
        "type": LocationType.hotel,
        "address": "88 Cascade Blvd",
        "lat": 28.6180,
        "lng": 77.1980,
    },
]

# seat_capacity, luggage_capacity, make_model mix
VEHICLE_PROFILES = [
    (4, 2, "Sedan"),
    (4, 3, "Sedan XL"),
    (6, 4, "SUV"),
    (7, 5, "MUV"),
    (12, 8, "Tempo Traveller"),
    (14, 10, "Mini Bus"),
]

# Disjoint pools so guest ↔ driver names never collide in demos
# (shared first+last previously made "Aarav Sharma" both a guest and a driver).
DRIVER_FIRST = [
    "Ravi", "Suresh", "Imran", "Deepak", "Harish", "Naveen", "Yusuf", "Balaji",
    "Farhan", "Gopal", "Jatin", "Karan", "Lalit", "Mohan", "Omkar", "Prakash",
    "Qadir", "Ramesh", "Sanjay", "Tushar", "Umesh", "Varun", "Wasim", "Yogesh",
    "Zubin",
]
DRIVER_LAST = [
    "Menon", "Pillai", "Shetty", "Bhat", "Kulkarni", "Deshmukh", "Naidu", "Hegde",
    "Saxena", "Trivedi", "Aggarwal", "Bansal", "Chawla", "Dhingra", "Eapen",
]

GUEST_FIRST = [
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Neha", "Arjun", "Isha",
    "Kabir", "Meera", "Dev", "Sana", "Nikhil", "Pooja", "Rahul", "Diya",
    "Aditya", "Kavya", "Siddharth", "Riya", "Manish", "Shreya", "Kunal", "Tara",
]
GUEST_LAST = [
    "Sharma", "Patel", "Singh", "Gupta", "Reddy", "Nair", "Khan", "Das",
    "Joshi", "Mehta", "Iyer", "Chopra", "Malhotra", "Banerjee", "Kapoor",
]

# Fixed demo identities (emails stay guest001@ / driver01@)
DEMO_DRIVER_NAME = "Ravi Menon"  # driver01@ — plate DL-1C-1000
DEMO_GUEST_NAME = "Priya Kapoor"  # guest001@


def _wipe(db: Session) -> None:
    # Order matters for FKs — use raw truncate cascade for seed reset
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    try:
        db.execute(
            text(
                "TRUNCATE assignment_events, location_pings, ride_requests, "
                "trip_guests, trip_stops, trips, event_schedules, guests, drivers, "
                "match_jobs, distance_cache, vehicles, locations, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.commit()
    except ProgrammingError:
        db.rollback()
        # Tables not created yet — caller should run alembic first
        raise RuntimeError("Database tables missing. Run: alembic upgrade head") from None


def seed(db: Session, *, reset: bool = True) -> None:
    random.seed(42)
    if reset:
        _wipe(db)
        # Postgres wipe does not clear Redis match queue — drop stale guest IDs
        try:
            from app.services.matching_service import clear_match_queue

            clear_match_queue()
        except Exception:
            pass

    # Admin
    admin = User(
        email="admin@smartdispatch.local",
        role=UserRole.admin,
        password_hash=hash_password("admin"),
        full_name="Ops Admin",
        phone="+910000000000",
    )
    db.add(admin)

    # Locations
    locs: dict[str, Location] = {}
    for spec in LOCATIONS:
        loc = Location(**spec)
        db.add(loc)
        locs[spec["name"]] = loc
    db.flush()

    airport = locs["Metro International Airport (T1)"]
    station = locs["Central Railway Station"]
    venue = locs["Grand Convention Venue"]
    hotels = [locs["Hotel Aurora"], locs["Hotel Meridian"], locs["Hotel Cascade"]]

    # Event day = next Saturday from a fixed anchor for reproducibility
    event_day = datetime(2026, 8, 8, tzinfo=timezone.utc)
    arrivals_start = event_day - timedelta(days=1)
    db.add_all(
        [
            EventSchedule(
                phase="arrivals",
                window_start=arrivals_start.replace(hour=6),
                window_end=arrivals_start.replace(hour=23),
                default_origin_id=airport.id,
                default_dest_id=hotels[0].id,
                trip_type=TripType.arrival,
            ),
            EventSchedule(
                phase="event_day_to_venue",
                window_start=event_day.replace(hour=7),
                window_end=event_day.replace(hour=10),
                default_origin_id=hotels[0].id,
                default_dest_id=venue.id,
                trip_type=TripType.to_venue,
            ),
            EventSchedule(
                phase="event_day_from_venue",
                window_start=event_day.replace(hour=17),
                window_end=event_day.replace(hour=21),
                default_origin_id=venue.id,
                default_dest_id=hotels[0].id,
                trip_type=TripType.from_venue,
            ),
            EventSchedule(
                phase="departures",
                window_start=(event_day + timedelta(days=1)).replace(hour=5),
                window_end=(event_day + timedelta(days=1)).replace(hour=22),
                default_origin_id=hotels[0].id,
                default_dest_id=airport.id,
                trip_type=TripType.departure,
            ),
        ]
    )

    # Drivers + vehicles (~25)
    n_drivers = 25
    for i in range(n_drivers):
        seats, luggage, make = VEHICLE_PROFILES[i % len(VEHICLE_PROFILES)]
        # Bias: more sedans than buses
        if i < 10:
            seats, luggage, make = 4, 2, "Sedan"
        elif i < 16:
            seats, luggage, make = 6, 4, "SUV"
        elif i < 21:
            seats, luggage, make = 7, 5, "MUV"
        else:
            seats, luggage, make = (12, 8, "Tempo Traveller") if i < 23 else (14, 10, "Mini Bus")

        vehicle = Vehicle(
            plate_number=f"DL-1C-{1000 + i}",
            seat_capacity=seats,
            luggage_capacity=luggage,
            make_model=make,
        )
        db.add(vehicle)
        db.flush()

        if i == 0:
            full_name = DEMO_DRIVER_NAME
        else:
            first = DRIVER_FIRST[i % len(DRIVER_FIRST)]
            last = DRIVER_LAST[(i * 3) % len(DRIVER_LAST)]
            full_name = f"{first} {last}"
        user = User(
            email=f"driver{i+1:02d}@smartdispatch.local",
            role=UserRole.driver,
            password_hash=hash_password("driver"),
            full_name=full_name,
            phone=f"+91987654{i:04d}",
        )
        db.add(user)
        db.flush()

        # Scatter near venue / hotels
        base = random.choice([venue, *hotels])
        db.add(
            Driver(
                user_id=user.id,
                vehicle_id=vehicle.id,
                status=DriverStatus.available,
                last_lat=base.lat + random.uniform(-0.01, 0.01),
                last_lng=base.lng + random.uniform(-0.01, 0.01),
                predicted_free_at=arrivals_start.replace(hour=6),
                predicted_free_lat=base.lat,
                predicted_free_lng=base.lng,
            )
        )

    # Guests (~150) with staggered arrivals
    n_guests = 150
    for i in range(n_guests):
        # ~70% airport, ~30% station
        pickup = airport if i % 10 < 7 else station
        hotel = hotels[i % len(hotels)]
        party = 1 if i % 5 else random.choice([2, 2, 3])
        if i % 40 == 0:
            party = random.choice([4, 5, 6])  # occasional large party
        luggage = party + (1 if pickup is airport else 0)

        # Stagger ETAs across arrival day 06:00–22:00
        minute_offset = (i * 7) % (16 * 60)  # spread over 16 hours
        eta = arrivals_start.replace(hour=6, minute=0, second=0) + timedelta(minutes=minute_offset)

        mode = "flight" if pickup is airport else "train"
        ref = f"{'AI' if mode == 'flight' else 'NR'}{100 + (i % 80)}"

        if i == 0:
            full_name = DEMO_GUEST_NAME
        else:
            first = GUEST_FIRST[(i * 5) % len(GUEST_FIRST)]
            last = GUEST_LAST[(i * 7) % len(GUEST_LAST)]
            full_name = f"{first} {last}"
        user = User(
            email=f"guest{i+1:03d}@smartdispatch.local",
            role=UserRole.guest,
            password_hash=hash_password("guest"),
            full_name=full_name,
            phone=f"+91876543{i:04d}",
        )
        db.add(user)
        db.flush()
        db.add(
            Guest(
                user_id=user.id,
                party_size=party,
                luggage_count=luggage,
                travel_eta=eta,
                travel_mode=mode,
                travel_ref=ref,
                pickup_location_id=pickup.id,
                accommodation_id=hotel.id,
                priority=(i % 25 == 0),  # ~6 VIPs
                attendance_status=AttendanceStatus.expected,
            )
        )

    db.commit()
    print(
        f"Seeded: 1 admin, {len(LOCATIONS)} locations, {n_drivers} drivers/vehicles, "
        f"{n_guests} guests, 4 schedule phases.\n"
        f"  Demo logins (password = role name):\n"
        f"    admin@smartdispatch.local  → Ops Admin\n"
        f"    driver01@…                 → {DEMO_DRIVER_NAME} (DL-1C-1000)\n"
        f"    guest001@…                 → {DEMO_GUEST_NAME}\n"
        f"  Driver names never overlap guest names (disjoint pools)."
    )


def main() -> None:
    # Ensure DB is reachable
    with engine.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    db = SessionLocal()
    try:
        seed(db, reset=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
