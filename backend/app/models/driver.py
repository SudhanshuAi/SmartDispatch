import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import DriverStatus


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    status: Mapped[DriverStatus] = mapped_column(
        Enum(DriverStatus, name="driver_status"), nullable=False, default=DriverStatus.offline
    )
    break_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    predicted_free_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    predicted_free_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_free_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="driver")  # noqa: F821
    vehicle: Mapped["Vehicle"] = relationship(back_populates="driver")  # noqa: F821
    trips: Mapped[list["Trip"]] = relationship(back_populates="driver")  # noqa: F821
    location_pings: Mapped[list["LocationPing"]] = relationship(back_populates="driver")  # noqa: F821
