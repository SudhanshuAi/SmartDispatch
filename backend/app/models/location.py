import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import LocationType


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[LocationType] = mapped_column(Enum(LocationType, name="location_type"), nullable=False)
    address: Mapped[str] = mapped_column(String(512), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    guests_pickup: Mapped[list["Guest"]] = relationship(  # noqa: F821
        back_populates="pickup_location", foreign_keys="Guest.pickup_location_id"
    )
    guests_accommodation: Mapped[list["Guest"]] = relationship(  # noqa: F821
        back_populates="accommodation", foreign_keys="Guest.accommodation_id"
    )
