"""Database access helpers for group records.

All functions accept an async SQLAlchemy session and perform queries or
writes against the ``groups`` table. Callers are responsible for opening the
session and resolving server-derived values such as the owning user's id.
"""

from uuid import UUID

from app.models.group_model import Group, Membership
from app.schemas.group_schema import GroupCreate
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