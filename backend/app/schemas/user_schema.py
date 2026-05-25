"""Pydantic schemas for user creation, input, and API responses.

These models validate HTTP payloads and serialize ORM ``User`` rows for the API.
``UserCreate`` accepts a raw password; hashing happens in the service layer
before persistence. ``UserResponse`` omits credentials and maps from SQLAlchemy
via ``from_attributes``.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared user fields used by both input and response schemas."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="The user's unique display name",
    )
    email: EmailStr = Field(..., description="The user's email address")


class UserCreate(UserBase):
    """Payload for registering a new user.

    The ``password`` field is validated here but must be hashed with
    ``get_password_hash`` before being written to ``User.hashed_password``.
    """

    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Raw, unhashed password",
    )


class UserResponse(UserBase):
    """User representation returned by the API.

    Excludes ``hashed_password`` and other internal-only columns. Populated
    from a ``User`` ORM instance when ``model_config.from_attributes`` is set.
    """

    id: UUID
    experience_points: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
