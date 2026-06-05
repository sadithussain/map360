"""ORM model definitions for groups and memberships.

A ``Group`` is the shared container that scopes map content: every member of a
group can later see contributions made by other members of the same group. A
``Membership`` is the join record linking a ``User`` to a ``Group`` along with
their role, enforcing that a user joins a given group at most once.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Group(Base):
    """A shared workspace that scopes map contributions to its members.

    Attributes:
        id: Primary key; UUID generated on insert.
        name: Human-readable group name.
        owner_id: Foreign key to the ``User`` who created the group.
        created_at: UTC timestamp set when the row is first created.
        owner: The owning ``User`` record.
        memberships: Membership rows connecting users to this group.
    """

    __tablename__ = "groups"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name = Column(String, nullable=False)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    owner = relationship("User", back_populates="owned_groups")
    memberships = relationship(
        "Membership",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Membership(Base):
    """Join record connecting a ``User`` to a ``Group`` with a role.

    A user can hold at most one membership per group, enforced by a unique
    constraint on ``(user_id, group_id)``.

    Attributes:
        id: Primary key; UUID generated on insert.
        user_id: Foreign key to the member ``User``.
        group_id: Foreign key to the ``Group`` joined.
        role: Membership role, e.g. ``owner`` or ``member``.
        joined_at: UTC timestamp set when the membership is created.
        user: The member ``User`` record.
        group: The ``Group`` this membership belongs to.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_membership_user_group"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id"),
        nullable=False,
        index=True,
    )
    role = Column(String, nullable=False, default="member")

    joined_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", back_populates="memberships")
    group = relationship("Group", back_populates="memberships")
