"""ORM model tracking a single-image 3D generation submission.

A ``MediaSubmission`` records one uploaded storefront photo and the async
TRELLIS generation job spawned for it. The row is created with status
``processing`` the moment the image is accepted; a FastAPI background task
later updates it to ``ready`` (with the generated mesh URLs) or ``failed``
(with an error message). The frontend polls this row to know when the mesh
is available.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

# Processing status values for a submission's generation job.
SUBMISSION_STATUS_PROCESSING = "processing"
SUBMISSION_STATUS_READY = "ready"
SUBMISSION_STATUS_FAILED = "failed"


class MediaSubmission(Base):
    """A single uploaded image and its TRELLIS generation job state.

    Attributes:
        id: Primary key; UUID generated on insert.
        group_id: Group the submission belongs to (privacy scope).
        pin_id: Location pin the generated model is anchored to.
        user_id: Member who uploaded the source image.
        source_image_key: Supabase Storage key of the uploaded photo.
        status: ``processing`` | ``ready`` | ``failed``.
        mesh_storage_key: Supabase Storage key of the generated ``.glb``.
        mesh_public_url: Public URL of the generated ``.glb``.
        error_message: Failure detail when ``status`` is ``failed``.
        created_at: UTC timestamp set when the row is first created.
        updated_at: UTC timestamp refreshed on each status transition.
    """

    __tablename__ = "media_submissions"

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
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    source_image_key = Column(String, nullable=False)
    status = Column(
        String,
        nullable=False,
        default=SUBMISSION_STATUS_PROCESSING,
        index=True,
    )
    mesh_storage_key = Column(String, nullable=True)
    mesh_public_url = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    group = relationship("Group")
    pin = relationship("LocationPin", back_populates="submissions")
    user = relationship("User")
    map_object = relationship(
        "MapObject",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )
