"""HTTP routes for groups.

Exposes group creation, listing the authenticated user's groups, and listing the
members of a group. The acting user is resolved from the validated Bearer token
via the auth dependency, so no owner or user id is accepted from the client.
"""

from uuid import UUID

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate, GroupResponse
from app.schemas.user_schema import UserResponse
from app.services.group_service import create_group as create_group_service, get_group_members as get_group_members_service, get_user_groups as get_user_groups_service
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post(
    "/create",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    group: GroupCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> GroupResponse:
    """Create a new group owned by the authenticated user.

    Identity comes from the validated Bearer token, so the owner is never
    trusted from the request. Delegates to the service layer, which creates
    the group and the owner's membership in a single transaction.
    """
    return await create_group_service(db, group, current_user)


@router.get(
    "/me",
    response_model=list[GroupResponse],
    status_code=status.HTTP_200_OK,
)
async def get_my_groups(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[GroupResponse]:
    """List all groups the authenticated user belongs to.

    Identity comes from the validated Bearer token, so no user id is accepted
    from the client. Returns every group the user is connected to through a
    membership, including groups they own and groups they have joined.
    """
    return await get_user_groups_service(db, current_user)


@router.get(
    "/{group_id}/members",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
async def get_group_members(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """List the members of the group with the given id.

    Identity comes from the validated Bearer token. The service layer enforces
    that the group exists and that the authenticated user belongs to it before
    any members are returned, preserving group privacy isolation.
    """
    return await get_group_members_service(db, group_id, current_user)
