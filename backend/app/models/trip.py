import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import StopType, TripStatus, TripType


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_type: Mapped[TripType] = mapped_column(Enum(TripType, name="trip_type"), nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus, name="trip_status"), nullable=False, default=TripStatus.planned
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    origin_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    dest_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_drop_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_pickup: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_drop: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seats_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    luggage_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    party_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    driver: Mapped["Driver | None"] = relationship(back_populates="trips")  # noqa: F821
    origin: Mapped["Location | None"] = relationship(foreign_keys=[origin_location_id])  # noqa: F821
    destination: Mapped["Location | None"] = relationship(foreign_keys=[dest_location_id])  # noqa: F821
    stops: Mapped[list["TripStop"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="TripStop.sequence"
    )
    trip_guests: Mapped[list["TripGuest"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )


class TripStop(Base):
    __tablename__ = "trip_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_type: Mapped[StopType] = mapped_column(Enum(StopType, name="stop_type"), nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="stops")
    guest: Mapped["Guest | None"] = relationship()  # noqa: F821
    location: Mapped["Location"] = relationship()  # noqa: F821


class TripGuest(Base):
    """Join of guests on a trip (shared rides / split groups)."""

    __tablename__ = "trip_guests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    luggage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dropped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="trip_guests")
    guest: Mapped["Guest"] = relationship(back_populates="trip_guests")  # noqa: F821
