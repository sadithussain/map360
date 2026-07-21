"""ORM model for a placed 3D object on a group's map.

A ``MapObject`` is created once a ``MediaSubmission`` finishes generating a
mesh. It links the generated ``.glb`` to a pin's real-world coordinates so the
frontend can render it on the group map. Keeping ``lat``/``lng`` and
``mesh_public_url`` denormalized here lets the map-state endpoint return
everything the renderer needs without extra joins.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class MapObject(Base):
    """A generated 3D model placed at a pin's location on the group map.

    Attributes:
        id: Primary key; UUID generated on insert.
        group_id: Group the object belongs to (privacy scope).
        pin_id: Location pin the object is anchored to.
        submission_id: Submission that produced this object.
        lat: Latitude copied from the pin for direct map placement.
        lng: Longitude copied from the pin for direct map placement.
        mesh_public_url: Public URL of the generated ``.glb`` mesh.
        created_at: UTC timestamp set when the row is first created.
    """

    __tablename__ = "map_objects"

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
    pin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("location_pins.id"),
        nullable=False,
        index=True,
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_submissions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    mesh_public_url = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    group = relationship("Group")
    pin = relationship("LocationPin", back_populates="map_objects")
    submission = relationship("MediaSubmission", back_populates="map_object")
