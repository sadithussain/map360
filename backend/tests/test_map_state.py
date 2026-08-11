"""Tests for ``GET /groups/{group_id}/map-state``."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.location_pin_crud import (
    create_location_pin as create_location_pin_crud,
)
from app.crud.location_pin_crud import list_location_pins_for_group
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Membership
from app.models.location_pin_model import LocationPin
from app.schemas.map_schema import (
    LocationPinCreate,
    LocationPinResponse,
    MapObjectResponse,
    MapStateResponse,
)
from app.services.map_service import create_location_pin as create_location_pin_service
from app.services.map_service import delete_all_location_pins as delete_all_location_pins_service
from app.services.map_service import delete_location_pin as delete_location_pin_service
from app.services.map_service import get_map_object as get_map_object_service
from app.services.map_service import get_map_state as get_map_state_service
from app.services.map_service import list_map_objects as list_map_objects_service
from app.services.map_service import (
    update_map_object_transform as update_map_object_transform_service,
)
from conftest import make_group as _make_group, make_map_object as _make_map_object, make_pin as _make_pin, make_user as _make_user
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

# A building footprint around (0, 0) plus a centroid inside it, used by the pin
# creation tests. Keeping them together makes the "inside vs outside" cases
# obvious.
_INSIDE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
}
_INSIDE_LAT = 0.5
_INSIDE_LNG = 0.5


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
async def test_map_object_response_defaults_scale_to_one(monkeypatch) -> None:
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

    assert result.scale == 1.0


@pytest.mark.asyncio
async def test_update_transform_normalizes_heading_and_clamps_scale(
    monkeypatch,
) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id)
    map_object = _make_map_object(pin)
    monkeypatch.setattr(
        "app.services.map_service.get_map_object_for_group",
        AsyncMock(return_value=map_object),
    )

    def _apply_transform(_db, obj, *, heading, scale):
        obj.heading = heading
        obj.scale = scale
        return obj

    crud_mock = AsyncMock(side_effect=_apply_transform)
    monkeypatch.setattr(
        "app.services.map_service.update_map_object_transform_crud", crud_mock
    )

    # Heading wraps into [0, 360) and out-of-range scale is clamped to the max.
    result = await update_map_object_transform_service(
        AsyncMock(), group.id, map_object.id, user, heading=450.0, scale=5.0
    )

    assert result.heading == 90.0
    assert result.scale == 2.0
    assert crud_mock.await_args.kwargs == {"heading": 90.0, "scale": 2.0}


@pytest.mark.asyncio
async def test_update_transform_404_when_missing(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    monkeypatch.setattr(
        "app.services.map_service.get_map_object_for_group",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_map_object_transform_service(
            AsyncMock(), group.id, uuid4(), user, heading=0.0, scale=1.0
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_transform_update_schema_rejects_out_of_range_scale() -> None:
    from pydantic import ValidationError

    from app.schemas.map_schema import MapObjectTransformUpdate

    with pytest.raises(ValidationError):
        MapObjectTransformUpdate(heading=0.0, scale=10.0)


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


# --- Location pin creation ------------------------------------------------


@pytest.mark.asyncio
async def test_create_pin_rejects_non_member(monkeypatch) -> None:
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
    create_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.map_service.create_location_pin_crud", create_mock
    )

    payload = LocationPinCreate(
        osm_building_id=123,
        lat=_INSIDE_LAT,
        lng=_INSIDE_LNG,
        building_geometry=_INSIDE_GEOMETRY,
        label="Cafe",
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_location_pin_service(AsyncMock(), group.id, user, payload)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_pin_rejects_centroid_outside_geometry(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    create_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.map_service.create_location_pin_crud", create_mock
    )

    # lat/lng sit far outside the (0, 0)-(1, 1) footprint bounds.
    payload = LocationPinCreate(
        osm_building_id=123,
        lat=40.5,
        lng=-73.9,
        building_geometry=_INSIDE_GEOMETRY,
        label=None,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_location_pin_service(AsyncMock(), group.id, user, payload)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_pin_persists_and_records_activity(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    pin = _make_pin(group.id, user.id, lat=_INSIDE_LAT, lng=_INSIDE_LNG, label="Cafe")
    create_mock = AsyncMock(return_value=pin)
    monkeypatch.setattr(
        "app.services.map_service.create_location_pin_crud", create_mock
    )
    activity_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.map_service.create_activity_event", activity_mock
    )

    payload = LocationPinCreate(
        osm_building_id=pin.osm_building_id,
        lat=_INSIDE_LAT,
        lng=_INSIDE_LNG,
        building_geometry=_INSIDE_GEOMETRY,
        label="Cafe",
    )
    db = AsyncMock()
    result = await create_location_pin_service(db, group.id, user, payload)

    assert isinstance(result, LocationPinResponse)
    assert result.id == pin.id
    create_mock.assert_awaited_once()
    # The contribution is recorded on the group's activity timeline and both the
    # pin and the event are committed in the same transaction.
    activity_mock.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_crud_create_location_pin_flushes_and_refreshes() -> None:
    db = AsyncMock()
    db.add = MagicMock()

    group_id = uuid4()
    user_id = uuid4()
    pin = await create_location_pin_crud(
        db,
        group_id=group_id,
        user_id=user_id,
        osm_building_id=456,
        lat=_INSIDE_LAT,
        lng=_INSIDE_LNG,
        building_geometry=_INSIDE_GEOMETRY,
        label="Bodega",
    )

    assert isinstance(pin, LocationPin)
    assert pin.group_id == group_id
    assert pin.user_id == user_id
    assert pin.osm_building_id == 456
    assert pin.label == "Bodega"
    db.add.assert_called_once_with(pin)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(pin)


@pytest.mark.asyncio
async def test_crud_list_location_pins_filters_by_group() -> None:
    group_id = uuid4()
    pins = [_make_pin(group_id, uuid4()), _make_pin(group_id, uuid4())]

    scalars = MagicMock()
    scalars.all.return_value = pins
    result = MagicMock()
    result.scalars.return_value = scalars

    db = AsyncMock()
    db.execute.return_value = result

    listed = await list_location_pins_for_group(db, group_id)

    assert listed == pins
    statement = db.execute.call_args.args[0]
    compiled = str(statement).lower()
    assert "location_pins.group_id" in compiled


def test_create_pin_endpoint_returns_201(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()
    pin = _make_pin(group_id, requester.id, lat=_INSIDE_LAT, lng=_INSIDE_LNG)

    service_mock = AsyncMock(return_value=LocationPinResponse.model_validate(pin))
    monkeypatch.setattr(
        "app.routers.map_router.create_location_pin_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            f"/groups/{group_id}/pins",
            json={
                "osm_building_id": pin.osm_building_id,
                "lat": _INSIDE_LAT,
                "lng": _INSIDE_LNG,
                "building_geometry": _INSIDE_GEOMETRY,
                "label": None,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(pin.id)
    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user, awaited_payload = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is requester
    assert awaited_payload.osm_building_id == pin.osm_building_id
