"""HTTP routes for group social / collaborative features.

Exposes the group activity feed (also used for the contributions log), the
map-growth chart, and the in-map discovery list. The acting user is resolved
from the validated Bearer token; the service layer enforces group membership so
activity stays isolated to the group.
"""

from datetime import datetime
from uuid import UUID

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.activity_schema import (
    ActivityListResponse,
    GrowthResponse,
    PlacesResponse,
)
from app.services.activity_service import (
    DEFAULT_ACTIVITY_LIMIT,
    DEFAULT_GROWTH_DAYS,
    MAX_ACTIVITY_LIMIT,
)
from app.services.activity_service import (
    get_group_activity as get_group_activity_service,
)
from app.services.activity_service import (
    get_group_growth as get_group_growth_service,
)
from app.services.activity_service import (
    get_group_places as get_group_places_service,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["social"])


@router.get(
    "/groups/{group_id}/activity",
    response_model=ActivityListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_group_activity(
    group_id: UUID,
    limit: int = Query(default=DEFAULT_ACTIVITY_LIMIT, ge=1, le=MAX_ACTIVITY_LIMIT),
    before: datetime | None = Query(default=None),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityListResponse:
    """Return recent activity events for a group the user belongs to.

    Pass ``before`` (the ``created_at`` of the oldest event you have) to page
    backwards through history for a "load more" control.
    """
    return await get_group_activity_service(
        db, group_id, current_user, limit=limit, before=before
    )


@router.get(
    "/groups/{group_id}/growth",
    response_model=GrowthResponse,
    status_code=status.HTTP_200_OK,
)
async def get_group_growth(
    group_id: UUID,
    days: int = Query(default=DEFAULT_GROWTH_DAYS, ge=1, le=365),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> GrowthResponse:
    """Return per-day model placements (and running total) for a group."""
    return await get_group_growth_service(db, group_id, current_user, days=days)


@router.get(
    "/groups/{group_id}/places",
    response_model=PlacesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_group_places(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> PlacesResponse:
    """Return a group's contributed places for the in-map discovery view."""
    return await get_group_places_service(db, group_id, current_user)
