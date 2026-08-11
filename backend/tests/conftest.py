"""Shared pytest fixtures, factories, and test environment setup.

The application settings require a Postgres connection URL and a JWT secret at
import time. Tests never touch a live database, so we populate the required
environment variables with safe placeholders before any application module is
imported. The async engine is created lazily and is never connected during the
unit/router tests in this suite.

This module also exposes small in-memory model builders (``make_user``,
``make_group``, ``make_membership``, ``make_pin``, ``make_map_object``,
``make_invite_code``). Column defaults only run on flush, so these set the
server-generated fields (``id``, ``created_at``, ...) explicitly to mimic a
persisted, refreshed row. Test modules import these from ``conftest`` to avoid
duplicating the same builders across files.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/postgres",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-of-sufficient-length")
os.environ.setdefault("ENVIRONMENT", "development")

from datetime import UTC, datetime  # noqa: E402
from uuid import uuid4  # noqa: E402

from app.models.group_model import Group, GroupInviteCode, Membership  # noqa: E402
from app.models.location_pin_model import LocationPin  # noqa: E402
from app.models.map_object_model import MapObject  # noqa: E402
from app.models.user_model import User  # noqa: E402


def make_user(username: str = "user") -> User:
    """Build an in-memory ``User`` with server-generated fields populated."""
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
    )
    user.id = uuid4()
    user.experience_points = 0
    user.created_at = datetime.now(UTC)
    return user


def make_group(owner_id, name: str = "Group") -> Group:
    """Build an in-memory ``Group`` owned by ``owner_id``."""
    group = Group(name=name, owner_id=owner_id)
    group.id = uuid4()
    group.created_at = datetime.now(UTC)
    return group


def make_membership(group_id, user_id, role: str = "member") -> Membership:
    """Build an in-memory ``Membership`` linking a user to a group."""
    membership = Membership(user_id=user_id, group_id=group_id, role=role)
    membership.id = uuid4()
    membership.joined_at = datetime.now(UTC)
    return membership


def make_invite_code(
    group_id,
    *,
    revoked_at=None,
    expires_at=None,
) -> GroupInviteCode:
    """Build an in-memory ``GroupInviteCode`` for a group."""
    invite_code = GroupInviteCode(
        group_id=group_id,
        code_hash="hash",
        created_by_id=uuid4(),
    )
    invite_code.id = uuid4()
    invite_code.created_at = datetime.now(UTC)
    invite_code.revoked_at = revoked_at
    invite_code.expires_at = expires_at
    return invite_code


def make_pin(
    group_id,
    user_id,
    *,
    osm_building_id: int = 123,
    lat: float = 40.5,
    lng: float = -73.9,
    label: str | None = None,
) -> LocationPin:
    """Build an in-memory ``LocationPin`` tied to a building footprint."""
    pin = LocationPin(
        group_id=group_id,
        user_id=user_id,
        osm_building_id=osm_building_id,
        lat=lat,
        lng=lng,
        building_geometry={"type": "Polygon", "coordinates": [[[0, 0]]]},
        label=label,
    )
    pin.id = uuid4()
    pin.created_at = datetime.now(UTC)
    return pin


def make_map_object(pin: LocationPin) -> MapObject:
    """Build an in-memory ``MapObject`` anchored to a pin.

    ``_map_object_to_response`` reads ``osm_building_id`` off the eager-loaded
    pin, so the relationship is populated here as the CRUD layer normally would.
    """
    map_object = MapObject(
        group_id=pin.group_id,
        pin_id=pin.id,
        submission_id=uuid4(),
        lat=pin.lat,
        lng=pin.lng,
        mesh_public_url="https://cdn/model.glb",
    )
    map_object.id = uuid4()
    map_object.created_at = datetime.now(UTC)
    map_object.pin = pin
    return map_object
