import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AttendanceStatus


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    luggage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    travel_eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    travel_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)  # flight | train
    travel_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)  # flight/train number
    pickup_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    accommodation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attendance_status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        nullable=False,
        default=AttendanceStatus.expected,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="guest")  # noqa: F821
    pickup_location: Mapped["Location | None"] = relationship(  # noqa: F821
        back_populates="guests_pickup", foreign_keys=[pickup_location_id]
    )
    accommodation: Mapped["Location | None"] = relationship(  # noqa: F821
        back_populates="guests_accommodation", foreign_keys=[accommodation_id]
    )
    trip_guests: Mapped[list["TripGuest"]] = relationship(back_populates="guest")  # noqa: F821
    ride_requests: Mapped[list["RideRequest"]] = relationship(back_populates="guest")  # noqa: F821
