"""Tests for group social features (activity feed, growth, discovery)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.activity_model import (
    ACTIVITY_EVENT_OBJECT_PLACED,
    ACTIVITY_EVENT_PIN_CREATED,
    ACTIVITY_TARGET_MAP_OBJECT,
    ACTIVITY_TARGET_PIN,
    ActivityEvent,
)
from app.models.group_model import Group, Membership
from app.models.location_pin_model import LocationPin
from app.models.map_object_model import MapObject
from app.models.media_submission_model import MediaSubmission
from app.models.user_model import User
from app.schemas.activity_schema import ActivityListResponse
from app.services.activity_service import (
    get_group_activity as get_group_activity_service,
)
from app.services.activity_service import (
    get_group_growth as get_group_growth_service,
)
from app.services.activity_service import (
    get_group_places as get_group_places_service,
)
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


def _make_user(username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", hashed_password="x")
    user.id = uuid4()
    user.created_at = datetime.now(UTC)
    return user


def _make_group(owner_id) -> Group:
    group = Group(name="Group", owner_id=owner_id)
    group.id = uuid4()
    group.created_at = datetime.now(UTC)
    return group


def _make_event(group_id, actor: User, *, created_at: datetime) -> ActivityEvent:
    event = ActivityEvent(
        group_id=group_id,
        actor_user_id=actor.id,
        event_type=ACTIVITY_EVENT_PIN_CREATED,
        target_type=ACTIVITY_TARGET_PIN,
        target_id=uuid4(),
        payload={"label": "Cafe", "lat": 40.5, "lng": -73.9},
    )
    event.id = uuid4()
    event.created_at = created_at
    event.actor = actor
    return event


def _pass_membership(monkeypatch, group) -> Membership:
    membership = Membership(user_id=group.owner_id, group_id=group.id, role="owner")
    monkeypatch.setattr(
        "app.services.activity_service.get_group_by_id",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.activity_service.get_membership_crud",
        AsyncMock(return_value=membership),
    )
    return membership


@pytest.mark.asyncio
async def test_activity_service_rejects_non_member(monkeypatch) -> None:
    user = _make_user("outsider")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        "app.services.activity_service.get_group_by_id",
        AsyncMock(return_value=group),
    )
    monkeypatch.setattr(
        "app.services.activity_service.get_membership_crud",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_group_activity_service(AsyncMock(), group.id, user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_activity_service_maps_actor_username(monkeypatch) -> None:
    actor = _make_user("alice")
    group = _make_group(actor.id)
    _pass_membership(monkeypatch, group)

    event = _make_event(group.id, actor, created_at=datetime.now(UTC))
    list_mock = AsyncMock(return_value=[event])
    monkeypatch.setattr(
        "app.services.activity_service.list_activity_events_for_group", list_mock
    )

    result = await get_group_activity_service(AsyncMock(), group.id, actor, limit=10)

    assert isinstance(result, ActivityListResponse)
    assert len(result.events) == 1
    assert result.events[0].actor_username == "alice"
    assert result.events[0].event_type == ACTIVITY_EVENT_PIN_CREATED
    # Limit is forwarded to the CRUD layer.
    assert list_mock.await_args.kwargs["limit"] == 10


@pytest.mark.asyncio
async def test_activity_service_clamps_limit(monkeypatch) -> None:
    actor = _make_user("alice")
    group = _make_group(actor.id)
    _pass_membership(monkeypatch, group)

    list_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.activity_service.list_activity_events_for_group", list_mock
    )

    await get_group_activity_service(AsyncMock(), group.id, actor, limit=99999)

    assert list_mock.await_args.kwargs["limit"] == 200


@pytest.mark.asyncio
async def test_growth_service_buckets_by_day(monkeypatch) -> None:
    actor = _make_user("alice")
    group = _make_group(actor.id)
    _pass_membership(monkeypatch, group)

    now = datetime.now(UTC)
    day_a = now - timedelta(days=2)
    day_b = now - timedelta(days=1)
    timestamps = [day_a, day_a, day_b]  # 2 on day_a, 1 on day_b

    monkeypatch.setattr(
        "app.services.activity_service.list_object_placed_timestamps_for_group",
        AsyncMock(return_value=timestamps),
    )

    result = await get_group_growth_service(AsyncMock(), group.id, actor, days=30)

    assert result.total == 3
    assert [p.count for p in result.points] == [2, 1]
    # Cumulative runs across the returned buckets.
    assert [p.cumulative for p in result.points] == [2, 3]


@pytest.mark.asyncio
async def test_places_service_builds_summaries(monkeypatch) -> None:
    contributor = _make_user("bob")
    group = _make_group(contributor.id)
    _pass_membership(monkeypatch, group)

    pin = LocationPin(
        group_id=group.id,
        user_id=contributor.id,
        osm_building_id=123,
        lat=40.5,
        lng=-73.9,
        building_geometry={"type": "Polygon", "coordinates": [[[0, 0]]]},
        label="Bodega",
    )
    pin.id = uuid4()
    submission = MediaSubmission(
        group_id=group.id,
        pin_id=pin.id,
        user_id=contributor.id,
        source_image_key="k",
    )
    submission.user = contributor
    obj = MapObject(
        group_id=group.id,
        pin_id=pin.id,
        submission_id=uuid4(),
        lat=pin.lat,
        lng=pin.lng,
        mesh_public_url="https://cdn/model.glb",
    )
    obj.id = uuid4()
    obj.created_at = datetime.now(UTC)
    obj.pin = pin
    obj.submission = submission

    monkeypatch.setattr(
        "app.services.activity_service.list_places_for_group",
        AsyncMock(return_value=[obj]),
    )

    result = await get_group_places_service(AsyncMock(), group.id, contributor)

    assert len(result.places) == 1
    place = result.places[0]
    assert place.label == "Bodega"
    assert place.contributor_username == "bob"
    assert place.pin_id == pin.id
    assert place.map_object_id == obj.id


def test_social_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/groups/{group_id}/activity" in paths
    assert "/groups/{group_id}/growth" in paths
    assert "/groups/{group_id}/places" in paths


def test_activity_endpoint_returns_events(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()
    expected = ActivityListResponse(events=[])

    service_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.routers.activity_router.get_group_activity_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(f"/groups/{group_id}/activity", params={"limit": 25})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"events": []}
    service_mock.assert_awaited_once()
    assert service_mock.await_args.kwargs["limit"] == 25


def test_activity_endpoint_rejects_bad_limit(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()

    service_mock = AsyncMock(return_value=ActivityListResponse(events=[]))
    monkeypatch.setattr(
        "app.routers.activity_router.get_group_activity_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(f"/groups/{group_id}/activity", params={"limit": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service_mock.assert_not_awaited()


def test_object_placed_constants_exist() -> None:
    # Guards the event/target vocabulary the frontend and backfill rely on.
    assert ACTIVITY_EVENT_OBJECT_PLACED == "object_placed"
    assert ACTIVITY_TARGET_MAP_OBJECT == "map_object"
