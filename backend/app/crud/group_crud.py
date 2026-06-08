"""Database access helpers for group records.

All functions accept an async SQLAlchemy session and perform queries or
writes against the ``groups`` table. Callers are responsible for opening the
session and resolving server-derived values such as the owning user's id.
"""

from uuid import UUID

from app.models.group_model import Group, Membership
from app.models.user_model import User
from app.schemas.group_schema import GroupCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def create_group(
    db: AsyncSession, group: GroupCreate, owner_id: UUID
) -> Group:
    """Persist a new group together with its owner membership.

    The ``owner_id`` is resolved from the authenticated user by the service
    layer rather than trusted from the request. The group and an ``owner``
    membership for the same user are created in a single transaction so a
    group is never persisted without its owner membership. Returns the
    refreshed ``Group`` instance (including server-generated fields).
    """
    db_group = Group(
        name=group.name,
        owner_id=owner_id,
    )
    db.add(db_group)
    await db.flush()

    db_membership = Membership(
        user_id=owner_id,
        group_id=db_group.id,
        role="owner",
    )
    db.add(db_membership)

    await db.commit()
    await db.refresh(db_group)

    return db_group

async def get_user_groups(
    db: AsyncSession,
    user_id: UUID,
) -> list[Group]:
    """Return every group the user belongs to via a membership.

    Joins the ``memberships`` table so the result includes both groups the
    user owns and groups they have joined. Ordered by ``created_at`` for a
    stable response. Returns a concrete list of ``Group`` instances.
    """
    statement = (
        select(Group)
        .join(Membership, Membership.group_id == Group.id)
        .where(Membership.user_id == user_id)
        .order_by(Group.created_at)
    )

    result = await db.execute(statement)

    return list(result.scalars().all())

async def get_group_by_id(
    db: AsyncSession,
    group_id: UUID,
) -> Group | None:
    """Return the group with the given id, or ``None`` if no match exists."""
    statement = select(Group).where(Group.id == group_id)

    result = await db.execute(statement)

    return result.scalar_one_or_none()


async def get_membership(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> Membership | None:
    """Return the membership linking a user to a group, or ``None``.

    A plain database read used by the service layer to decide whether a user is
    permitted to act on a group. No authorization decision is made here.
    """
    statement = select(Membership).where(
        Membership.group_id == group_id,
        Membership.user_id == user_id,
    )

    result = await db.execute(statement)

    return result.scalar_one_or_none()


async def get_group_members(
    db: AsyncSession,
    group_id: UUID,
) -> list[User]:
    """Return the users that belong to the given group via a membership.

    Joins ``users`` through ``memberships`` so members are resolved with a
    single query rather than via lazy-loaded relationships. Ordered by
    ``username`` for a stable response. Returns a concrete list of ``User``
    instances.
    """
    statement = (
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.group_id == group_id)
        .order_by(User.username)
    )

    result = await db.execute(statement)

    return list(result.scalars().all())
