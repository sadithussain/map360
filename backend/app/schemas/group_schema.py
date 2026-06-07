"""Pydantic schemas for group and membership input and API responses.

These models validate HTTP payloads and serialize ORM ``Group`` and
``Membership`` rows for the API. Request schemas accept only client-supplied
fields; server-derived values such as the owning user's id or generated
identifiers are populated in the service layer. Response schemas map from
SQLAlchemy instances via ``from_attributes``.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GroupBase(BaseModel):
    """Shared group fields used by both input and response schemas."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable group name",
    )


class GroupCreate(GroupBase):
    """Payload for creating a new group.

    Only the ``name`` is accepted from the client; the owner is resolved from
    the authenticated user in the service layer, not trusted from the request.
    """


class GroupResponse(GroupBase):
    """Group representation returned by the API.

    Populated from a ``Group`` ORM instance when ``model_config.from_attributes``
    is set.
    """

    id: UUID
    owner_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipBase(BaseModel):
    """Shared membership fields used by both input and response schemas."""

    role: str = Field(
        default="member",
        max_length=50,
        description="Membership role within the group, e.g. 'owner' or 'member'",
    )


class MembershipCreate(MembershipBase):
    """Payload for creating a membership (joining a group).

    The ``group_id`` identifies the target group; the member is resolved from
    the authenticated user in the service layer rather than trusted from the
    request body.
    """

    group_id: UUID = Field(..., description="The group the user is joining")


class MembershipResponse(MembershipBase):
    """Membership representation returned by the API.

    Populated from a ``Membership`` ORM instance when
    ``model_config.from_attributes`` is set.
    """

    id: UUID
    user_id: UUID
    group_id: UUID
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
