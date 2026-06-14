"""Tests for the group permission helpers.

Covers the service-level helpers ``is_group_member`` and ``is_group_owner`` in
[``app.services.group_service``]:

* ``is_group_member`` raises ``404`` for a missing group, returns ``False`` when
  the group exists but the user has no membership, and ``True`` when a
  membership exists.
* ``is_group_owner`` raises ``404`` for a missing group, returns ``False`` when
  the authenticated user is not the owner, and ``True`` when ``group.owner_id``
  matches the authenticated user.

These tests deliberately avoid a live database: the CRUD calls the helpers
delegate to are replaced with ``AsyncMock`` via ``monkeypatch``.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.models.group_model import Group, Membership
from app.models.user_model import User
from app.services.group_service import is_group_member as is_group_member_service, is_group_owner as is_group_owner_service
from fastapi import HTTPException, status
from unittest.mock import AsyncMock


def _make_user(username: str) -> User:
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


def _make_group(owner_id) -> Group:
    group = Group(name="Group", owner_id=owner_id)
    group.id = uuid4()
    group.created_at = datetime.now(UTC)
    return group


def _make_membership(group_id, user_id, role: str = "member") -> Membership:
    membership = Membership(user_id=user_id, group_id=group_id, role=role)
    membership.id = uuid4()
    membership.joined_at = datetime.now(UTC)
    return membership


# --- is_group_member ------------------------------------------------------


@pytest.mark.asyncio
async def test_is_group_member_raises_404_for_missing_group(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )
    membership_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud", membership_mock
    )

    user = _make_user("user")
    with pytest.raises(HTTPException) as exc_info:
        await is_group_member_service(AsyncMock(), uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    membership_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_is_group_member_returns_false_for_non_member(monkeypatch) -> None:
    group = _make_group(uuid4())
    outsider = _make_user("outsider")

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=None),
    )

    result = await is_group_member_service(AsyncMock(), group.id, outsider)

    assert result is False


@pytest.mark.asyncio
async def test_is_group_member_returns_true_for_member(monkeypatch) -> None:
    member = _make_user("member")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=_make_membership(group.id, member.id)),
    )

    result = await is_group_member_service(AsyncMock(), group.id, member)

    assert result is True


# --- is_group_owner -------------------------------------------------------


@pytest.mark.asyncio
async def test_is_group_owner_raises_404_for_missing_group(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )

    user = _make_user("user")
    with pytest.raises(HTTPException) as exc_info:
        await is_group_owner_service(AsyncMock(), uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_is_group_owner_returns_false_for_non_owner(monkeypatch) -> None:
    group = _make_group(uuid4())
    requester = _make_user("not-owner")

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )

    result = await is_group_owner_service(AsyncMock(), group.id, requester)

    assert result is False


@pytest.mark.asyncio
async def test_is_group_owner_returns_true_for_owner(monkeypatch) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )

    result = await is_group_owner_service(AsyncMock(), group.id, owner)

    assert result is True
