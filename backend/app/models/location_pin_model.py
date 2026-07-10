"""ORM model for building-tied location pins on a group's map."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class LocationPin(Base):
    """A contribution anchor tied to a base-map building footprint.

    Pins are scoped to a group and created by a member. Multiple pins may
    reference the same ``osm_building_id`` within a group when users re-scan
    a building.
    """

    __tablename__ = "location_pins"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    osm_building_id = Column(BigInteger, nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    building_geometry = Column(JSONB, nullable=False)
    label = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    group = relationship("Group", back_populates="location_pins")
    user = relationship("User", back_populates="location_pins")
