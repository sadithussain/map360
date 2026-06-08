"""Business logic for groups.

Orchestrates group use cases and delegates persistence to the CRUD layer.
Routers should depend on this module rather than calling CRUD directly.
"""

from app.crud.group_crud import create_group as create_group_crud, get_user_groups as get_user_groups_crud
from app.models.group_model import Group
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate
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
