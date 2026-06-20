"""ORM model definitions for application users.

The User table is the central identity record. It links to the groups a user
owns and the memberships connecting them to groups; content-submission
relationships remain deferred until those models are implemented.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    """Persisted user account with profile and gamification fields.

    Attributes:
        id: Primary key; UUID generated on insert.
        username: Unique display name, indexed for lookup.
        email: Unique login contact, indexed for lookup.
        hashed_password: bcrypt digest from ``app.core.security``; never plain text.
        experience_points: Cumulative XP earned across the platform.
        created_at: UTC timestamp set when the row is first created.
        owned_groups: Groups this user created and owns.
        memberships: Membership rows linking this user to groups they belong to.
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    experience_points = Column(Integer, default=0, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    owned_groups = relationship(
        "Group",
        back_populates="owner",
    )
    memberships = relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
