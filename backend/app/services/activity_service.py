"""Business logic for group social / collaborative features.

Exposes read paths for the activity feed (and contributions log), the map-growth
chart, and the in-map discovery list. All paths enforce group membership so
activity stays isolated to the group, matching the map-state routes.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.crud.activity_crud import (
    list_activity_events_for_group,
    list_object_placed_timestamps_for_group,
    list_places_for_group,
)
from app.crud.group_crud import get_membership as get_membership_crud
from app.models.activity_model import ActivityEvent
from app.models.map_object_model import MapObject
from app.models.user_model import User
from app.schemas.activity_schema import (
    ActivityEventResponse,
    ActivityListResponse,
    GrowthPoint,
    GrowthResponse,
    PlacesResponse,
    PlaceSummary,
)
from app.services.group_service import get_group_by_id
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# Default number of events returned by the feed in a single page.
DEFAULT_ACTIVITY_LIMIT = 50
MAX_ACTIVITY_LIMIT = 200

# Default window (in days) for the map-growth chart.
DEFAULT_GROWTH_DAYS = 30


async def _require_group_membership(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> None:
    """Raise 404 if the group is missing, 403 if the user is not a member."""
    await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )


def _event_to_response(event: ActivityEvent) -> ActivityEventResponse:
    """Build a feed response, resolving the actor's username from the relation.

    Assumes ``event.actor`` was eager-loaded by the CRUD layer. Falls back to a
    placeholder if the acting user record is unexpectedly missing.
    """
    actor_username = event.actor.username if event.actor is not None else "Unknown"
    return ActivityEventResponse(
        id=event.id,
        event_type=event.event_type,
        actor_user_id=event.actor_user_id,
        actor_username=actor_username,
        target_type=event.target_type,
        target_id=event.target_id,
        payload=event.payload,
        created_at=event.created_at,
    )


def _place_to_summary(obj: MapObject) -> PlaceSummary:
    """Build a discovery summary from a map object with pin + submission loaded."""
    label = obj.pin.label if obj.pin is not None else None
    contributor = None
    if obj.submission is not None and obj.submission.user is not None:
        contributor = obj.submission.user.username
    return PlaceSummary(
        pin_id=obj.pin_id,
        map_object_id=obj.id,
        label=label,
        lat=obj.lat,
        lng=obj.lng,
        contributor_username=contributor,
        created_at=obj.created_at,
    )


async def get_group_activity(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
    *,
    limit: int = DEFAULT_ACTIVITY_LIMIT,
    before: datetime | None = None,
) -> ActivityListResponse:
    """Return recent activity events for a group the user belongs to."""
    await _require_group_membership(db, group_id, current_user)

    bounded_limit = max(1, min(MAX_ACTIVITY_LIMIT, limit))
    events = await list_activity_events_for_group(
        db, group_id, limit=bounded_limit, before=before
    )
    return ActivityListResponse(events=[_event_to_response(event) for event in events])


async def get_group_growth(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
    *,
    days: int = DEFAULT_GROWTH_DAYS,
) -> GrowthResponse:
    """Return per-day model placements and a running cumulative for a group.

    Buckets ``object_placed`` events by UTC calendar day over the trailing
    ``days`` window. Days with no placements are omitted; ``cumulative`` counts
    all placements up to and including each returned day (including any before
    the window), and ``total`` is the group's all-time placement count.
    """
    await _require_group_membership(db, group_id, current_user)

    bounded_days = max(1, days)
    cutoff = datetime.now(UTC) - timedelta(days=bounded_days)

    # All-time timestamps drive the cumulative baseline; the window only limits
    # which daily buckets are returned.
    timestamps = await list_object_placed_timestamps_for_group(db, group_id)

    per_day: dict[str, int] = {}
    for ts in timestamps:
        day = ts.astimezone(UTC).date().isoformat()
        per_day[day] = per_day.get(day, 0) + 1

    cutoff_day = cutoff.date().isoformat()
    running = 0
    points: list[GrowthPoint] = []
    for day in sorted(per_day):
        running += per_day[day]
        if day >= cutoff_day:
            points.append(GrowthPoint(date=day, count=per_day[day], cumulative=running))

    return GrowthResponse(points=points, total=len(timestamps))


async def get_group_places(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> PlacesResponse:
    """Return a group's contributed places for the in-map discovery view."""
    await _require_group_membership(db, group_id, current_user)

    objects = await list_places_for_group(db, group_id)
    return PlacesResponse(places=[_place_to_summary(obj) for obj in objects])
