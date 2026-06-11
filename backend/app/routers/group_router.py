"""HTTP routes for groups.

Exposes group creation, joining via invite code, invite-code generation, listing
the authenticated user's groups, listing the members of a group, leaving a group,
and removing a member from a group. The acting user is resolved from the
validated Bearer token via the auth dependency, so no owner or user id is
accepted from the client.
"""

from uuid import UUID

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate, GroupInviteCodeResponse, GroupJoinRequest, GroupResponse, MembershipResponse
from app.schemas.user_schema import UserResponse
from app.services.group_service import create_group as create_group_service, create_group_invite_code as create_group_invite_code_service, get_group_members as get_group_members_service, get_user_groups as get_user_groups_service, join_group_by_invite_code as join_group_by_invite_code_service, leave_group as leave_group_service, remove_group_member as remove_group_member_service
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


@router.post(
    "/join",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_group(
    request: GroupJoinRequest,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> MembershipResponse:
    """Join the authenticated user to a group using a reusable invite code.

    Identity comes from the validated Bearer token, so the joining user is
    never trusted from the request. The service validates the invite code,
    rejects revoked or expired codes, prevents duplicate memberships, and
    creates a ``member`` membership on success.
    """
    return await join_group_by_invite_code_service(db, request, current_user)


@router.post(
    "/{group_id}/invite-code",
    response_model=GroupInviteCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite_code(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> GroupInviteCodeResponse:
    """Generate a reusable invite code for a group the user owns.

    Identity comes from the validated Bearer token. The service enforces that
    the group exists and that the authenticated user owns it before generating
    a code. The raw code is returned only here, since only its hash is stored.
    """
    return await create_group_invite_code_service(db, group_id, current_user)


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


@router.delete(
    "/{group_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_group(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the authenticated user's own membership from a group.

    Identity comes from the validated Bearer token. The service raises ``404``
    if the group does not exist, ``403`` if the user is not a member, and
    ``409`` if the user owns the group. Responds with ``204 No Content``.
    """
    await leave_group_service(db, group_id, current_user)


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove another member from a group the authenticated user owns.

    Identity comes from the validated Bearer token. The service enforces that
    the group exists, that the requester owns it, that the target is not the
    owner, and that the target is a member before deleting the membership.
    Responds with ``204 No Content``.
    """
    await remove_group_member_service(db, group_id, user_id, current_user)