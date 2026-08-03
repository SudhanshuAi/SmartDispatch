import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import RideRequestStatus


class RideRequest(Base):
    __tablename__ = "ride_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    origin_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    dest_location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    luggage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RideRequestStatus] = mapped_column(
        Enum(RideRequestStatus, name="ride_request_status"),
        nullable=False,
        default=RideRequestStatus.pending_admin,
    )
    wait_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trip_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trips.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    guest: Mapped["Guest"] = relationship(back_populates="ride_requests")  # noqa: F821
