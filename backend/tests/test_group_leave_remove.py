"""Tests for leaving a group and removing a member from a group.

Covers the three layers of the two ``DELETE`` membership endpoints:

* CRUD: ``remove_membership`` issues a ``DELETE`` filtered by ``group_id`` and
  ``user_id``, commits, and reports whether a row was deleted.
* Service: ``leave_group`` rejects a missing group (``404``), a non-member
  (``403``), and an owner trying to leave (``409``); ``remove_group_member``
  rejects a non-owner (``403``), removing the owner (``409``), and a target that
  is not a member (``404``), deleting the membership on success.
* Router: ``DELETE /groups/{group_id}/members/me`` and
  ``DELETE /groups/{group_id}/members/{user_id}`` require an authenticated user
  and respond with ``204 No Content``; the old verb-first leave path is gone.

These tests deliberately avoid a live database: CRUD is exercised with a mocked
``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.group_crud import remove_membership as remove_membership_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.services.group_service import leave_group as leave_group_service, remove_group_member as remove_group_member_service
from conftest import make_group as _make_group, make_membership as _make_membership, make_user as _make_user
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


# --- CRUD -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_remove_membership_deletes_and_reports_true() -> None:
    group_id = uuid4()
    user_id = uuid4()

    result = MagicMock()
    result.rowcount = 1

    db = AsyncMock()
    db.execute.return_value = result

    deleted = await remove_membership_crud(db, group_id, user_id)

    assert deleted is True
    db.commit.assert_awaited_once()

    statement = db.execute.call_args.args[0]
    compiled = str(statement).lower()
    assert "delete from memberships" in compiled
    assert "memberships.group_id" in compiled
    assert "memberships.user_id" in compiled


@pytest.mark.asyncio
async def test_crud_remove_membership_reports_false_when_no_row() -> None:
    result = MagicMock()
    result.rowcount = 0

    db = AsyncMock()
    db.execute.return_value = result

    deleted = await remove_membership_crud(db, uuid4(), uuid4())

    assert deleted is False


# --- Service: leave -------------------------------------------------------


@pytest.mark.asyncio
async def test_service_leave_raises_404_for_missing_group(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    member = _make_user("member")
    with pytest.raises(HTTPException) as exc_info:
        await leave_group_service(AsyncMock(), uuid4(), member)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_leave_raises_403_for_non_member(monkeypatch) -> None:
    group = _make_group(uuid4())
    requester = _make_user("outsider")

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=None),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await leave_group_service(AsyncMock(), group.id, requester)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_leave_raises_409_for_owner(monkeypatch) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=_make_membership(group.id, owner.id, "owner")),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await leave_group_service(AsyncMock(), group.id, owner)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_leave_deletes_membership_for_member(monkeypatch) -> None:
    owner = _make_user("owner")
    member = _make_user("member")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=_make_membership(group.id, member.id)),
    )
    remove_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    db = AsyncMock()
    result = await leave_group_service(db, group.id, member)

    assert result is None
    remove_mock.assert_awaited_once_with(db, group.id, member.id)


# --- Service: remove member -----------------------------------------------


@pytest.mark.asyncio
async def test_service_remove_raises_404_for_missing_group(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    owner = _make_user("owner")
    with pytest.raises(HTTPException) as exc_info:
        await remove_group_member_service(
            AsyncMock(), uuid4(), uuid4(), owner
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_remove_raises_403_for_non_owner(monkeypatch) -> None:
    group = _make_group(uuid4())
    requester = _make_user("not-owner")

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await remove_group_member_service(
            AsyncMock(), group.id, uuid4(), requester
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_remove_raises_409_for_owner_target(monkeypatch) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await remove_group_member_service(
            AsyncMock(), group.id, owner.id, owner
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_remove_raises_404_for_non_member_target(
    monkeypatch,
) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=None),
    )
    remove_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await remove_group_member_service(
            AsyncMock(), group.id, uuid4(), owner
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_remove_deletes_membership_for_owner(monkeypatch) -> None:
    owner = _make_user("owner")
    target = _make_user("target")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=_make_membership(group.id, target.id)),
    )
    remove_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.services.group_service.remove_membership_crud", remove_mock
    )

    db = AsyncMock()
    result = await remove_group_member_service(db, group.id, target.id, owner)

    assert result is None
    remove_mock.assert_awaited_once_with(db, group.id, target.id)


# --- Router ---------------------------------------------------------------


def test_leave_group_endpoint_returns_204(monkeypatch) -> None:
    member = _make_user("member")
    group_id = uuid4()

    service_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.routers.group_router.leave_group_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: member
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.delete(f"/groups/{group_id}/members/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""

    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is member


def test_remove_member_endpoint_returns_204(monkeypatch) -> None:
    owner = _make_user("owner")
    group_id = uuid4()
    user_id = uuid4()

    service_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.routers.group_router.remove_group_member_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: owner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.delete(f"/groups/{group_id}/members/{user_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""

    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user_id, awaited_user = (
        service_mock.await_args.args
    )
    assert awaited_group_id == group_id
    assert awaited_user_id == user_id
    assert awaited_user is owner


def test_leave_remove_routes_are_registered() -> None:
    group_paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/groups")
    }

    assert "/groups/{group_id}/members/me" in group_paths
    assert "/groups/{group_id}/members/{user_id}" in group_paths
    assert "/groups/leave/{group_id}" not in group_paths
