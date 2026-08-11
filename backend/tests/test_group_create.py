"""Tests for creating a group (``POST /groups/create``).

Covers the three layers of group creation:

* CRUD: ``create_group`` persists the group and an ``owner`` membership in one
  transaction, then commits and refreshes.
* Service: ``create_group`` resolves the owner from the authenticated user and
  delegates to CRUD.
* Router: the endpoint requires an authenticated user and serializes to a
  ``GroupResponse``.

These tests deliberately avoid a live database: CRUD is exercised with a mocked
``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.group_crud import create_group as create_group_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Group, Membership
from app.schemas.group_schema import GroupCreate
from app.services.group_service import create_group as create_group_service
from conftest import make_group as _make_group, make_user as _make_user
from fastapi.testclient import TestClient


# --- CRUD -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_create_group_persists_group_and_owner_membership() -> None:
    db = AsyncMock()
    db.add = MagicMock()

    owner_id = uuid4()
    group = await create_group_crud(db, GroupCreate(name="Explorers"), owner_id)

    assert isinstance(group, Group)
    assert group.name == "Explorers"
    assert group.owner_id == owner_id

    # The group and its owner membership are added in the same transaction.
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(obj, Group) for obj in added)
    membership = next(obj for obj in added if isinstance(obj, Membership))
    assert membership.user_id == owner_id
    assert membership.role == "owner"

    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(group)


# --- Service --------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_create_group_delegates_with_owner_id(monkeypatch) -> None:
    owner = _make_user("owner")
    expected = _make_group(owner.id, name="Explorers")

    crud_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.services.group_service.create_group_crud", crud_mock
    )

    db = AsyncMock()
    payload = GroupCreate(name="Explorers")
    result = await create_group_service(db, payload, owner)

    assert result is expected
    crud_mock.assert_awaited_once_with(db, payload, owner.id)


# --- Router ---------------------------------------------------------------


def test_create_group_endpoint_returns_serialized_group(monkeypatch) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id, name="Explorers")

    service_mock = AsyncMock(return_value=group)
    monkeypatch.setattr(
        "app.routers.group_router.create_group_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: owner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post("/groups/create", json={"name": "Explorers"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Explorers"
    assert body["id"] == str(group.id)
    assert body["owner_id"] == str(owner.id)

    service_mock.assert_awaited_once()
    _, awaited_payload, awaited_user = service_mock.await_args.args
    assert awaited_payload.name == "Explorers"
    assert awaited_user is owner


def test_create_group_endpoint_rejects_empty_name() -> None:
    owner = _make_user("owner")

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: owner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post("/groups/create", json={"name": ""})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
