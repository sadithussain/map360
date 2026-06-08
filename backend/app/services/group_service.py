"""Business logic for groups.

Orchestrates group use cases and delegates persistence to the CRUD layer.
Routers should depend on this module rather than calling CRUD directly.
"""

from uuid import UUID

from app.crud.group_crud import create_group as create_group_crud, get_group_by_id as get_group_by_id_crud, get_group_members as get_group_members_crud, get_membership as get_membership_crud, get_user_groups as get_user_groups_crud
from app.models.group_model import Group
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def create_group(
    db: AsyncSession, group: GroupCreate, owner: User
) -> Group:
    """Create a new group owned by the authenticated user.

    The owner is taken from the authenticated ``User`` rather than the request
    body. Delegates to the CRUD layer, which also creates the owner's
    membership in the same transaction.
    """
    return await create_group_crud(db, group, owner.id)

async def get_user_groups(
    db: AsyncSession,
    user: User,
) -> list[Group]:
    """List all groups the given user belongs to.

    The user is taken from the authenticated ``User`` rather than a client
    supplied id. Delegates to the CRUD layer, which resolves every group the
    user is connected to through a membership.
    """
    return await get_user_groups_crud(db, user.id)

async def get_group_by_id(
    db: AsyncSession,
    group_id: UUID,
) -> Group:
    """Return the group with the given id.

    Delegates the lookup to the CRUD layer and raises ``404`` when the group
    does not exist.
    """
    group = await get_group_by_id_crud(db, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with id {group_id} not found",
        )
    return group


async def get_group_members(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> list[User]:
    """Return the members of a group the authenticated user belongs to.

    Raises ``404`` if the group does not exist and ``403`` if the authenticated
    user is not a member of it, preserving group privacy isolation. The actual
    member rows are resolved by the CRUD layer.
    """
    await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )

    return await get_group_members_crud(db, group_id)
