"""Initial schema for SmartDispatch domain model.

Revision ID: 001_initial
Revises:
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = postgresql.ENUM("admin", "driver", "guest", name="user_role", create_type=False)
location_type = postgresql.ENUM("airport", "station", "venue", "hotel", name="location_type", create_type=False)
driver_status = postgresql.ENUM(
    "offline", "available", "en_route", "at_pickup", "in_trip", "on_break", name="driver_status", create_type=False
)
attendance_status = postgresql.ENUM(
    "expected", "checked_in", "no_show", "cancelled", name="attendance_status", create_type=False
)
trip_type = postgresql.ENUM(
    "arrival", "to_venue", "from_venue", "departure", "on_demand", name="trip_type", create_type=False
)
trip_status = postgresql.ENUM(
    "planned",
    "offered",
    "accepted",
    "en_route",
    "at_pickup",
    "in_progress",
    "completed",
    "cancelled",
    name="trip_status",
    create_type=False,
)
stop_type = postgresql.ENUM("pickup", "drop", name="stop_type", create_type=False)
ride_request_status = postgresql.ENUM(
    "pending_admin",
    "approved",
    "queued",
    "matched",
    "declined",
    "cancelled",
    name="ride_request_status",
    create_type=False,
)
assignment_source = postgresql.ENUM(
    "batch", "greedy", "detour", "override", "placeholder", name="assignment_source", create_type=False
)
match_job_status = postgresql.ENUM(
    "pending", "running", "completed", "failed", name="match_job_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_t in (
        sa.Enum("admin", "driver", "guest", name="user_role"),
        sa.Enum("airport", "station", "venue", "hotel", name="location_type"),
        sa.Enum(
            "offline", "available", "en_route", "at_pickup", "in_trip", "on_break", name="driver_status"
        ),
        sa.Enum("expected", "checked_in", "no_show", "cancelled", name="attendance_status"),
        sa.Enum("arrival", "to_venue", "from_venue", "departure", "on_demand", name="trip_type"),
        sa.Enum(
            "planned",
            "offered",
            "accepted",
            "en_route",
            "at_pickup",
            "in_progress",
            "completed",
            "cancelled",
            name="trip_status",
        ),
        sa.Enum("pickup", "drop", name="stop_type"),
        sa.Enum(
            "pending_admin",
            "approved",
            "queued",
            "matched",
            "declined",
            "cancelled",
            name="ride_request_status",
        ),
        sa.Enum("batch", "greedy", "detour", "override", "placeholder", name="assignment_source"),
        sa.Enum("pending", "running", "completed", "failed", name="match_job_status"),
    ):
        enum_t.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", location_type, nullable=False),
        sa.Column("address", sa.String(512), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plate_number", sa.String(32), nullable=False),
        sa.Column("seat_capacity", sa.Integer(), nullable=False),
        sa.Column("luggage_capacity", sa.Integer(), nullable=False),
        sa.Column("make_model", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("plate_number", name="uq_vehicles_plate_number"),
    )

    op.create_table(
        "distance_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("od_hash", sa.String(128), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("distance_meters", sa.Integer(), nullable=False),
        sa.Column("traffic_ttl_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_distance_cache_od_hash", "distance_cache", ["od_hash"], unique=True)

    op.create_table(
        "match_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", match_job_status, nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "drivers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", driver_status, nullable=False),
        sa.Column("break_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("predicted_free_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("predicted_free_lat", sa.Float(), nullable=True),
        sa.Column("predicted_free_lng", sa.Float(), nullable=True),
        sa.Column("last_lat", sa.Float(), nullable=True),
        sa.Column("last_lng", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("vehicle_id"),
    )

    op.create_table(
        "guests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("luggage_count", sa.Integer(), nullable=False),
        sa.Column("travel_eta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("travel_mode", sa.String(32), nullable=True),
        sa.Column("travel_ref", sa.String(64), nullable=True),
        sa.Column("pickup_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accommodation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("attendance_status", attendance_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "event_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("default_origin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_dest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trip_type", trip_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_type", trip_type, nullable=False),
        sa.Column("status", trip_status, nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("origin_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dest_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_drop_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta_pickup", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta_drop", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seats_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("luggage_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("route_polyline", sa.Text(), nullable=True),
        sa.Column("route_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("party_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_party_group_id", "trips", ["party_group_id"])

    op.create_table(
        "trip_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stop_type", stop_type, nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trip_stops_trip_id", "trip_stops", ["trip_id"])

    op.create_table(
        "trip_guests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("luggage", sa.Integer(), nullable=False),
        sa.Column("boarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_trip_guests_trip_id", "trip_guests", ["trip_id"])
    op.create_index("ix_trip_guests_guest_id", "trip_guests", ["guest_id"])

    op.create_table(
        "ride_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dest_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("luggage_count", sa.Integer(), nullable=False),
        sa.Column("status", ride_request_status, nullable=False),
        sa.Column("wait_started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ride_requests_guest_id", "ride_requests", ["guest_id"])

    op.create_table(
        "location_pings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_location_pings_driver_id", "location_pings", ["driver_id"])
    op.create_index("ix_location_pings_recorded_at", "location_pings", ["recorded_at"])

    op.create_table(
        "assignment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("guests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", assignment_source, nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_assignment_events_trip_id", "assignment_events", ["trip_id"])


def downgrade() -> None:
    op.drop_table("assignment_events")
    op.drop_table("location_pings")
    op.drop_table("ride_requests")
    op.drop_table("trip_guests")
    op.drop_table("trip_stops")
    op.drop_table("trips")
    op.drop_table("event_schedules")
    op.drop_table("guests")
    op.drop_table("drivers")
    op.drop_table("match_jobs")
    op.drop_table("distance_cache")
    op.drop_table("vehicles")
    op.drop_table("locations")
    op.drop_table("users")

    bind = op.get_bind()
    for name in (
        "match_job_status",
        "assignment_source",
        "ride_request_status",
        "stop_type",
        "trip_status",
        "trip_type",
        "attendance_status",
        "driver_status",
        "location_type",
        "user_role",
    ):
        sa.Enum(name=name).drop(bind, checkfirst=True)
