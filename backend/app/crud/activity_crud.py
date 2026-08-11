"""Database access helpers for group activity events.

Covers writing activity events at contribution milestones and reading them back
for the feed, the map-growth chart, and the discovery list. The service layer
owns transactions and authorization; these helpers only read and write rows.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.models.activity_model import (
    ACTIVITY_EVENT_OBJECT_PLACED,
    ActivityEvent,
)
from app.models.map_object_model import MapObject
from app.models.media_submission_model import MediaSubmission
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def create_activity_event(
    db: AsyncSession,
    *,
    group_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    target_type: str,
    target_id: UUID | None,
    payload: dict[str, Any] | None,
) -> ActivityEvent:
    """Append an activity event. Flushes but does not commit.

    The caller is expected to commit as part of the same transaction that
    created the underlying pin or map object, so the feed never drifts from the
    content it describes.
    """
    event = ActivityEvent(
        group_id=group_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )
    db.add(event)
    await db.flush()
    return event


async def list_activity_events_for_group(
    db: AsyncSession,
    group_id: UUID,
    *,
    limit: int,
    before: datetime | None = None,
) -> list[ActivityEvent]:
    """Return a group's activity events, newest first.

    Eager-loads the acting user so callers can read ``actor.username`` without a
    lazy load. When ``before`` is given, only events strictly older than it are
    returned (keyset pagination for "load more").
    """
    query = (
        select(ActivityEvent)
        .options(selectinload(ActivityEvent.actor))
        .where(ActivityEvent.group_id == group_id)
    )
    if before is not None:
        query = query.where(ActivityEvent.created_at < before)
    query = query.order_by(ActivityEvent.created_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def list_object_placed_timestamps_for_group(
    db: AsyncSession,
    group_id: UUID,
    *,
    since: datetime | None = None,
) -> list[datetime]:
    """Return the timestamps of ``object_placed`` events for a group, ascending.

    Used to build the map-growth chart by bucketing placements per day. When
    ``since`` is given, only events at or after it are returned.
    """
    query = select(ActivityEvent.created_at).where(
        ActivityEvent.group_id == group_id,
        ActivityEvent.event_type == ACTIVITY_EVENT_OBJECT_PLACED,
    )
    if since is not None:
        query = query.where(ActivityEvent.created_at >= since)
    query = query.order_by(ActivityEvent.created_at.asc())

    result = await db.execute(query)
    return [row for row in result.scalars().all() if row is not None]


async def list_places_for_group(
    db: AsyncSession,
    group_id: UUID,
) -> list[MapObject]:
    """Return a group's placed map objects for the discovery list, newest first.

    Eager-loads the anchoring pin (for label/coordinates) and the submission's
    uploader (for contributor attribution) so the service can build place
    summaries without extra queries.
    """
    query = (
        select(MapObject)
        .options(
            selectinload(MapObject.pin),
            selectinload(MapObject.submission).selectinload(MediaSubmission.user),
        )
        .where(MapObject.group_id == group_id)
        .order_by(MapObject.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())
