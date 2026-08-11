"""ORM model for group activity events.

An ``ActivityEvent`` is an append-only record of a noteworthy action inside a
group's shared world: a member pinning a building, or a generated mesh being
placed on the map. Events power the group activity feed, the contributions
log, and the map-growth chart without re-deriving history from the underlying
pins/objects on every request.

Events are polymorphic: ``target_type`` names what the event is about
(``pin`` or ``map_object``) and ``target_id`` is that row's id. A denormalized
``payload`` snapshot (label, coordinates, osm building id) lets the feed render
without extra joins even if the target is later removed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

# Event types recorded on a group's activity timeline.
ACTIVITY_EVENT_PIN_CREATED = "pin_created"
ACTIVITY_EVENT_OBJECT_PLACED = "object_placed"

# Target kinds an event can point at.
ACTIVITY_TARGET_PIN = "pin"
ACTIVITY_TARGET_MAP_OBJECT = "map_object"


class ActivityEvent(Base):
    """A single timestamped action within a group's shared map.

    Attributes:
        id: Primary key; UUID generated on insert.
        group_id: Group the event belongs to (privacy scope).
        actor_user_id: The member who performed the action.
        event_type: ``pin_created`` | ``object_placed``.
        target_type: ``pin`` | ``map_object``; what the event is about.
        target_id: Id of the target row (kept even if the row is later deleted).
        payload: Denormalized snapshot (label, lat, lng, osm_building_id, ...)
            so the feed can render without joining the target.
        created_at: UTC timestamp set when the event is recorded.
    """

    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_group_created_at", "group_id", "created_at"),
    )

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
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

    group = relationship("Group")
    actor = relationship("User")
