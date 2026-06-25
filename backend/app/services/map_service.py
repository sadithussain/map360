"""Business logic for group map state."""

from uuid import UUID

from app.crud.group_crud import get_membership as get_membership_crud
from app.models.user_model import User
from app.schemas.map_schema import MapStateResponse
from app.services.group_service import get_group_by_id
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_map_state(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> MapStateResponse:
    """Return the map state for a group the authenticated user belongs to.

    Raises ``404`` if the group does not exist and ``403`` if the user is not
    a member. Until location pins and map objects are implemented, returns an
    empty default state.
    """
    await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )

    return MapStateResponse(group_id=group_id, pins=[], objects=[])
