"""Pydantic schemas for user creation, input, and API responses.

These models validate HTTP payloads and serialize ORM ``User`` rows for the API.
``UserCreate`` accepts a raw password; hashing happens in the service layer
before persistence. ``UserResponse`` omits credentials and maps from SQLAlchemy
via ``from_attributes``.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Shared constraint bounds, reused by the Pydantic fields below and by the
# service layer so frontend, schema, and service validation never drift apart.
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 100


class UserBase(BaseModel):
    """Shared user fields used by both input and response schemas."""

    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
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
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
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


class UserLogin(BaseModel):
    """Payload for authenticating an existing user."""

    email: EmailStr = Field(..., description="The user's email address")
    password: str = Field(..., description="Raw, unhashed password")


class UserPasswordChange(BaseModel):
    """Payload for changing the authenticated user's password.

    The ``current_password`` is verified against the stored hash in the service
    layer before ``new_password`` is hashed and persisted. ``new_password``
    enforces the same length rules as registration.
    """

    current_password: str = Field(
        ...,
        description="The user's current, unhashed password",
    )
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="The new, raw, unhashed password",
    )


class Token(BaseModel):
    """Access token issued after a successful login."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(
        default="bearer",
        description="Token type for the Authorization header",
    )
