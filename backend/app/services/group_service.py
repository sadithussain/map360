"""Business logic for groups.

Orchestrates group use cases and delegates persistence to the CRUD layer.
Routers should depend on this module rather than calling CRUD directly.
"""

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from app.crud.group_crud import create_group as create_group_crud, create_group_invite_code as create_group_invite_code_crud, create_membership as create_membership_crud, get_group_by_id as get_group_by_id_crud, get_group_members as get_group_members_crud, get_invite_code_by_hash as get_invite_code_by_hash_crud, get_membership as get_membership_crud, get_user_groups as get_user_groups_crud, remove_membership as remove_membership_crud
from app.models.group_model import Group, Membership
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate, GroupInviteCodeResponse, GroupJoinRequest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


def _hash_invite_code(raw_code: str) -> str:
    """Return the SHA-256 hex digest used to store and look up an invite code."""
    return hashlib.sha256(raw_code.strip().encode("utf-8")).hexdigest()


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


def _is_expired(expires_at: datetime | None) -> bool:
    """Return ``True`` if the given expiry timestamp is in the past.

    Stored timestamps may be timezone-naive (Postgres ``DateTime``), so a naive
    value is treated as UTC before comparison.
    """
    if expires_at is None:
        return False

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return expires_at <= datetime.now(UTC)


async def join_group_by_invite_code(
    db: AsyncSession,
    request: GroupJoinRequest,
    current_user: User,
) -> Membership:
    """Join the authenticated user to a group using a reusable invite code.

    The submitted code is hashed and looked up; an unknown code yields ``404``
    while a revoked or expired code yields ``400``. A user who already belongs
    to the target group yields ``409``. On success a ``member`` membership is
    created and returned. Identity comes from the authenticated ``User`` rather
    than the request body.
    """
    code_hash = _hash_invite_code(request.invite_code)
    invite_code = await get_invite_code_by_hash_crud(db, code_hash)
    if invite_code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code.",
        )

    if invite_code.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite code has been revoked.",
        )

    if _is_expired(invite_code.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite code has expired.",
        )

    existing = await get_membership_crud(
        db, invite_code.group_id, current_user.id
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this group.",
        )

    return await create_membership_crud(
        db, invite_code.group_id, current_user.id, role="member"
    )


async def create_group_invite_code(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> GroupInviteCodeResponse:
    """Generate a reusable invite code for a group the user owns.

    Raises ``404`` if the group does not exist and ``403`` if the authenticated
    user is not its owner. A cryptographically random code is generated and
    only its hash is persisted; the raw code is returned once so the owner can
    share it.
    """
    group = await get_group_by_id(db, group_id)

    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can create invite codes.",
        )

    raw_code = secrets.token_urlsafe(16)
    invite_code = await create_group_invite_code_crud(
        db,
        group_id,
        current_user.id,
        _hash_invite_code(raw_code),
    )

    return GroupInviteCodeResponse(
        group_id=invite_code.group_id,
        invite_code=raw_code,
        created_at=invite_code.created_at,
        expires_at=invite_code.expires_at,
    )


async def is_group_member(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> bool:
    """Return ``True`` if the authenticated user is a member of the group.

    Raises ``404`` if the group does not exist. Returns ``False`` when the user
    has no membership in the group.
    """
    await get_group_by_id(db, group_id)
    membership = await get_membership_crud(db, group_id, current_user.id)
    return membership is not None


async def is_group_owner(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> bool:
    """Return ``True`` if the authenticated user owns the given group.

    Raises ``404`` if the group does not exist. Ownership is resolved from the
    group's ``owner_id`` rather than the membership role, which is the
    authoritative source of truth.
    """
    group = await get_group_by_id(db, group_id)
    return group.owner_id == current_user.id


async def leave_group(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> None:
    """Remove the authenticated user's own membership from a group.

    Raises ``404`` if the group does not exist, ``403`` if the user is not a
    member of it, and ``409`` if the user owns the group (an owner must transfer
    ownership before leaving). Deletes the membership row on success.
    """
    group = await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )

    if group.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The group owner cannot leave the group.",
        )

    await remove_membership_crud(db, group_id, current_user.id)


async def remove_group_member(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
    current_user: User,
) -> None:
    """Remove another member from a group the authenticated user owns.

    Raises ``404`` if the group does not exist, ``403`` if the authenticated
    user is not the group owner, ``409`` if the target is the owner (the owner
    cannot be removed), and ``404`` if the target user is not a member. Deletes
    the target membership row on success.
    """
    group = await get_group_by_id(db, group_id)

    if group.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can remove members.",
        )

    if user_id == group.owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The group owner cannot be removed from the group.",
        )

    membership = await get_membership_crud(db, group_id, user_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This user is not a member of the group.",
        )

    await remove_membership_crud(db, group_id, user_id)