"""ORM model definitions for groups and memberships.

A ``Group`` is the shared container that scopes map content: every member of a
group can later see contributions made by other members of the same group. A
``Membership`` is the join record linking a ``User`` to a ``Group`` along with
their role, enforcing that a user joins a given group at most once. A
``GroupInviteCode`` is a reusable secret that lets a user join a group without
exposing the group's raw id as the join secret.
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
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    owner = relationship("User", back_populates="owned_groups")
    memberships = relationship(
        "Membership",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    invite_codes = relationship(
        "GroupInviteCode",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    location_pins = relationship(
        "LocationPin",
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
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user = relationship("User", back_populates="memberships")
    group = relationship("Group", back_populates="memberships")


class GroupInviteCode(Base):
    """A reusable secret that grants membership to a single ``Group``.

    Only the SHA-256 hash of the raw code is stored, so a leaked database row
    cannot be replayed as a join secret. A code may optionally expire and may
    be revoked, letting a group owner rotate codes without deleting history.

    Attributes:
        id: Primary key; UUID generated on insert.
        group_id: Foreign key to the ``Group`` this code grants access to.
        code_hash: SHA-256 hex digest of the raw invite code; unique.
        created_by_id: Foreign key to the ``User`` who generated the code.
        created_at: UTC timestamp set when the code is created.
        expires_at: Optional UTC timestamp after which the code is invalid.
        revoked_at: Optional UTC timestamp marking the code as revoked.
        group: The ``Group`` this code belongs to.
    """

    __tablename__ = "group_invite_codes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id"),
        nullable=False,
        index=True,
    )
    code_hash = Column(String, nullable=False, unique=True, index=True)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    group = relationship("Group", back_populates="invite_codes")
