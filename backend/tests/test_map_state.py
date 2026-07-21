"""Tests for ``GET /groups/{group_id}/map-state``."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Group, Membership
from app.models.user_model import User
from app.schemas.map_schema import MapStateResponse
from app.services.map_service import get_map_state as get_map_state_service
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


def _make_user(username: str) -> User:
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
async def test_service_raises_404_for_missing_group(monkeypatch) -> None:
    user = _make_user("member")
    group_id = uuid4()

    async def _raise_404(*_args, **_kwargs):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with id {group_id} not found",
        )

    monkeypatch.setattr(
        "app.services.map_service.get_group_by_id",
        _raise_404,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_map_state_service(AsyncMock(), group_id, user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_service_raises_403_for_non_member(monkeypatch) -> None:
    user = _make_user("outsider")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        "app.services.map_service.get_group_by_id",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.map_service.get_membership_crud",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_map_state_service(AsyncMock(), group.id, user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_service_returns_empty_default_for_member(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    membership = Membership(user_id=user.id, group_id=group.id, role="member")

    monkeypatch.setattr(
        "app.services.map_service.get_group_by_id",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.map_service.get_membership_crud",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.services.map_service.list_location_pins_for_group",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.map_service.list_map_objects_for_group",
        AsyncMock(return_value=[]),
    )

    result = await get_map_state_service(AsyncMock(), group.id, user)

    assert result == MapStateResponse(group_id=group.id, pins=[], objects=[])


def test_get_map_state_endpoint_returns_empty_state(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()
    expected = MapStateResponse(group_id=group_id, pins=[], objects=[])

    service_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.routers.map_router.get_map_state_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(f"/groups/{group_id}/map-state")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()
    assert body["group_id"] == str(group_id)
    assert body["pins"] == []
    assert body["objects"] == []

    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is requester


def test_map_state_route_is_registered() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/groups/{group_id}/map-state" in paths
    assert "/groups/{group_id}/pins" in paths
