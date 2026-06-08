"""Tests for listing the authenticated user's groups.

Covers the three layers of the ``GET /groups/me`` flow:

* CRUD: the query joins ``memberships`` so both owned and joined groups are
  returned, and the result is a concrete ``list[Group]``.
* Service: delegates to CRUD using ``user.id`` from the authenticated ``User``.
* Router: the endpoint is exposed at ``/groups/me`` (token-derived identity, no
  client-supplied ``user_id``) and serializes to ``list[GroupResponse]``.

These tests deliberately avoid a live database: the CRUD layer is exercised with
a mocked ``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.group_crud import get_user_groups as get_user_groups_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Group
from app.models.user_model import User
from app.services.group_service import get_user_groups as get_user_groups_service
from fastapi.testclient import TestClient


def _make_group(name: str, owner_id) -> Group:
    """Build an in-memory ``Group`` with server-generated fields populated.

    Column defaults only run on flush, so ``id`` and ``created_at`` are set
    explicitly to mimic a persisted, refreshed row.
    """
    group = Group(name=name, owner_id=owner_id)
    group.id = uuid4()
    group.created_at = datetime.now(UTC)
    return group


@pytest.mark.asyncio
async def test_crud_queries_memberships_and_returns_list() -> None:
    user_id = uuid4()
    owned = _make_group("Owned", user_id)
    joined = _make_group("Joined", uuid4())

    scalars = MagicMock()
    scalars.all.return_value = [owned, joined]
    result = MagicMock()
    result.scalars.return_value = scalars

    db = AsyncMock()
    db.execute.return_value = result

    groups = await get_user_groups_crud(db, user_id)

    assert groups == [owned, joined]
    assert isinstance(groups, list)

    statement = db.execute.call_args.args[0]
    compiled = str(statement).lower()
    assert "join memberships" in compiled
    assert "memberships.user_id" in compiled


@pytest.mark.asyncio
async def test_service_delegates_with_user_id(monkeypatch) -> None:
    user = User(username="alice", email="alice@example.com", hashed_password="x")
    user.id = uuid4()

    expected = [_make_group("Owned", user.id)]
    crud_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.services.group_service.get_user_groups_crud", crud_mock
    )

    db = AsyncMock()
    result = await get_user_groups_service(db, user)

    assert result == expected
    crud_mock.assert_awaited_once_with(db, user.id)


def test_get_my_groups_endpoint_returns_serialized_list(monkeypatch) -> None:
    user = User(username="bob", email="bob@example.com", hashed_password="x")
    user.id = uuid4()

    owned = _make_group("Owned", user.id)
    joined = _make_group("Joined", uuid4())

    service_mock = AsyncMock(return_value=[owned, joined])
    monkeypatch.setattr(
        "app.routers.group_router.get_user_groups_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get("/groups/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert [item["name"] for item in body] == ["Owned", "Joined"]
    assert body[0]["id"] == str(owned.id)
    assert body[0]["owner_id"] == str(user.id)

    service_mock.assert_awaited_once()
    _, awaited_user = service_mock.await_args.args
    assert awaited_user is user


def test_current_user_route_has_no_user_id_path_param() -> None:
    group_paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/groups")
    }

    assert "/groups/me" in group_paths
    assert not any("{user_id}" in path for path in group_paths)
