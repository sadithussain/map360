"""Tests for listing the members of a group.

Covers the three layers of the ``GET /groups/{group_id}/members`` flow:

* CRUD: ``get_group_members`` joins ``users`` through ``memberships`` and returns
  a concrete ``list[User]``; ``get_membership`` resolves a single membership.
* Service: enforces ``404`` for a missing group and ``403`` for a requester that
  is not a member, then delegates member resolution to CRUD.
* Router: the endpoint is exposed at ``/groups/{group_id}/members``, requires an
  authenticated user, and serializes to ``list[UserResponse]``.

These tests deliberately avoid a live database: CRUD is exercised with a mocked
``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.group_crud import get_group_members as get_group_members_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Group, Membership
from app.models.user_model import User
from app.services.group_service import get_group_members as get_group_members_service
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


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


@pytest.mark.asyncio
async def test_crud_queries_members_through_memberships() -> None:
    group_id = uuid4()
    alice = _make_user("alice")
    bob = _make_user("bob")

    scalars = MagicMock()
    scalars.all.return_value = [alice, bob]
    result = MagicMock()
    result.scalars.return_value = scalars

    db = AsyncMock()
    db.execute.return_value = result

    members = await get_group_members_crud(db, group_id)

    assert members == [alice, bob]
    assert isinstance(members, list)

    statement = db.execute.call_args.args[0]
    compiled = str(statement).lower()
    assert "join memberships" in compiled
    assert "memberships.group_id" in compiled


@pytest.mark.asyncio
async def test_service_raises_404_for_missing_group(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )

    requester = _make_user("requester")
    with pytest.raises(HTTPException) as exc_info:
        await get_group_members_service(AsyncMock(), uuid4(), requester)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_service_raises_403_for_non_member(monkeypatch) -> None:
    requester = _make_user("outsider")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=None),
    )
    members_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.get_group_members_crud", members_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_group_members_service(AsyncMock(), group.id, requester)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    members_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_returns_members_for_member(monkeypatch) -> None:
    requester = _make_user("member")
    group = _make_group(requester.id)
    expected = [requester, _make_user("other")]

    membership = Membership(
        user_id=requester.id, group_id=group.id, role="member"
    )

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_group_members_crud",
        AsyncMock(return_value=expected),
    )

    db = AsyncMock()
    result = await get_group_members_service(db, group.id, requester)

    assert result == expected


def test_get_group_members_endpoint_returns_serialized_list(monkeypatch) -> None:
    requester = _make_user("requester")
    members = [_make_user("alice"), _make_user("bob")]
    group_id = uuid4()

    service_mock = AsyncMock(return_value=members)
    monkeypatch.setattr(
        "app.routers.group_router.get_group_members_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(f"/groups/{group_id}/members")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()
    assert [item["username"] for item in body] == ["alice", "bob"]
    assert body[0]["id"] == str(members[0].id)
    assert "hashed_password" not in body[0]

    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is requester


def test_members_route_is_registered() -> None:
    group_paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/groups")
    }

    assert "/groups/{group_id}/members" in group_paths
