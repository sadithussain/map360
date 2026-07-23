"""Tests for ``GET /groups/{group_id}/map-state``."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Group, Membership
from app.models.location_pin_model import LocationPin
from app.models.map_object_model import MapObject
from app.models.user_model import User
from app.schemas.map_schema import MapObjectResponse, MapStateResponse
from app.services.map_service import delete_all_location_pins as delete_all_location_pins_service
from app.services.map_service import delete_location_pin as delete_location_pin_service
from app.services.map_service import get_map_object as get_map_object_service
from app.services.map_service import get_map_state as get_map_state_service
from app.services.map_service import list_map_objects as list_map_objects_service
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


def _make_pin(group_id, user_id) -> LocationPin:
    pin = LocationPin(
        group_id=group_id,
        user_id=user_id,
        osm_building_id=123,
        lat=40.5,
        lng=-73.9,
        building_geometry={"type": "Polygon", "coordinates": [[[0, 0]]]},
        label=None,
    )
    pin.id = uuid4()
    pin.created_at = datetime.now(UTC)
    return pin


def _make_map_object(pin: LocationPin) -> MapObject:
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
    # ``_map_object_to_response`` reads ``osm_building_id`` off the eager-loaded
    # pin; the CRUD layer normally populates this relationship.
    map_object.pin = pin
    return map_object


def _pass_membership(monkeypatch, group) -> Membership:
    membership = Membership(
        user_id=group.owner_id, group_id=group.id, role="owner"
    )
    monkeypatch.setattr(
        "app.services.map_service.get_group_by_id",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.map_service.get_membership_crud",
        AsyncMock(return_value=membership),
    )
    return membership


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
        "app.services.map_service.list_rendered_location_pins_for_group",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.map_service.list_map_objects_for_group",
        AsyncMock(return_value=[]),
    )

    result = await get_map_state_service(AsyncMock(), group.id, user)

    assert result == MapStateResponse(group_id=group.id, pins=[], objects=[])


@pytest.mark.asyncio
async def test_map_state_returns_only_rendered_pins(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    rendered_pin = _make_pin(group.id, user.id)
    # The service relies on ``list_rendered_location_pins_for_group`` (which
    # filters to pins that have a map object) rather than every pin.
    rendered_mock = AsyncMock(return_value=[rendered_pin])
    monkeypatch.setattr(
        "app.services.map_service.list_rendered_location_pins_for_group",
        rendered_mock,
    )
    monkeypatch.setattr(
        "app.services.map_service.list_map_objects_for_group",
        AsyncMock(return_value=[]),
    )

    result = await get_map_state_service(AsyncMock(), group.id, user)

    rendered_mock.assert_awaited_once()
    assert [pin.id for pin in result.pins] == [rendered_pin.id]


@pytest.mark.asyncio
async def test_map_state_object_carries_pin_osm_building_id(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id)
    pin.osm_building_id = 987654
    map_object = _make_map_object(pin)

    monkeypatch.setattr(
        "app.services.map_service.list_rendered_location_pins_for_group",
        AsyncMock(return_value=[pin]),
    )
    monkeypatch.setattr(
        "app.services.map_service.list_map_objects_for_group",
        AsyncMock(return_value=[map_object]),
    )

    result = await get_map_state_service(AsyncMock(), group.id, user)

    assert len(result.objects) == 1
    assert result.objects[0].osm_building_id == 987654
    assert result.objects[0].mesh_url == "https://cdn/model.glb"


@pytest.mark.asyncio
async def test_list_map_objects_service_returns_objects(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id)
    map_object = _make_map_object(pin)
    list_mock = AsyncMock(return_value=[map_object])
    monkeypatch.setattr(
        "app.services.map_service.list_map_objects_for_group", list_mock
    )

    result = await list_map_objects_service(
        AsyncMock(), group.id, user, bbox=(-74.0, 40.0, -73.0, 41.0)
    )

    assert [obj.id for obj in result] == [map_object.id]
    # The bbox is forwarded to the CRUD layer as a keyword argument.
    assert list_mock.await_args.kwargs["bbox"] == (-74.0, 40.0, -73.0, 41.0)


@pytest.mark.asyncio
async def test_get_map_object_service_404_when_missing(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    monkeypatch.setattr(
        "app.services.map_service.get_map_object_for_group",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_map_object_service(AsyncMock(), group.id, uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_map_object_service_returns_object(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id)
    map_object = _make_map_object(pin)
    monkeypatch.setattr(
        "app.services.map_service.get_map_object_for_group",
        AsyncMock(return_value=map_object),
    )

    result = await get_map_object_service(
        AsyncMock(), group.id, map_object.id, user
    )

    assert isinstance(result, MapObjectResponse)
    assert result.id == map_object.id
    assert result.osm_building_id == pin.osm_building_id


@pytest.mark.asyncio
async def test_delete_pin_rejects_non_member(monkeypatch) -> None:
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
        await delete_location_pin_service(AsyncMock(), group.id, uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_delete_pin_404_when_missing_or_other_group(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    # Pin belongs to a different group, so it must not be deletable here.
    other_group_pin = _make_pin(uuid4(), user.id)
    monkeypatch.setattr(
        "app.services.map_service.get_location_pin_crud",
        AsyncMock(return_value=other_group_pin),
    )
    delete_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.map_service.delete_location_pin_crud", delete_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await delete_location_pin_service(
            AsyncMock(), group.id, other_group_pin.id, user
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_pin_success_calls_crud_and_commits(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id)
    monkeypatch.setattr(
        "app.services.map_service.get_location_pin_crud",
        AsyncMock(return_value=pin),
    )
    delete_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.map_service.delete_location_pin_crud", delete_mock
    )

    db = AsyncMock()
    await delete_location_pin_service(db, group.id, pin.id, user)

    delete_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


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
    assert "/groups/{group_id}/pins/{pin_id}" in paths
    assert "/groups/{group_id}/map-objects" in paths
    assert "/groups/{group_id}/map-objects/{object_id}" in paths


def test_list_map_objects_endpoint_rejects_partial_bbox(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()

    service_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.routers.map_router.list_map_objects_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(
            f"/groups/{group_id}/map-objects", params={"min_lng": -74.0}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service_mock.assert_not_awaited()


def test_list_map_objects_endpoint_forwards_full_bbox(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()

    service_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.routers.map_router.list_map_objects_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(
            f"/groups/{group_id}/map-objects",
            params={
                "min_lng": -74.0,
                "min_lat": 40.0,
                "max_lng": -73.0,
                "max_lat": 41.0,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    service_mock.assert_awaited_once()
    assert service_mock.await_args.kwargs["bbox"] == (-74.0, 40.0, -73.0, 41.0)


def test_delete_pin_endpoint_returns_204(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()
    pin_id = uuid4()

    service_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.routers.map_router.delete_location_pin_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.delete(f"/groups/{group_id}/pins/{pin_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_pin_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_pin_id == pin_id
    assert awaited_user is requester


@pytest.mark.asyncio
async def test_delete_all_pins_success_calls_crud_and_commits(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    delete_all_mock = AsyncMock(return_value=3)
    monkeypatch.setattr(
        "app.services.map_service.delete_all_location_pins_for_group_crud",
        delete_all_mock,
    )

    db = AsyncMock()
    deleted = await delete_all_location_pins_service(db, group.id, user)

    assert deleted == 3
    delete_all_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


def test_delete_all_pins_endpoint_returns_count(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()

    service_mock = AsyncMock(return_value=5)
    monkeypatch.setattr(
        "app.routers.map_router.delete_all_location_pins_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.delete(f"/groups/{group_id}/pins")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"deleted": 5}
    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is requester
