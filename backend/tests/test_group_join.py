"""Tests for joining a group via a reusable invite code.

Covers the three layers of the ``POST /groups/join`` flow plus the owner-only
``POST /groups/{group_id}/invite-code`` supporting endpoint:

* CRUD: ``create_membership`` inserts and refreshes a ``Membership``;
  ``get_invite_code_by_hash`` filters on the stored hash;
  ``create_group_invite_code`` persists only the code hash.
* Service: ``join_group_by_invite_code`` rejects unknown (``404``), revoked and
  expired (``400``) codes, blocks duplicate memberships (``409``), and creates a
  ``member`` membership on success; ``create_group_invite_code`` enforces
  ``404``/``403`` and returns the raw code once.
* Router: both endpoints require an authenticated user and serialize correctly.

These tests deliberately avoid a live database: CRUD is exercised with a mocked
``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.crud.group_crud import create_group_invite_code as create_group_invite_code_crud, create_membership as create_membership_crud, get_invite_code_by_hash as get_invite_code_by_hash_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import GroupInviteCode, Membership
from app.schemas.group_schema import GroupInviteCodeResponse, GroupJoinRequest
from app.services.group_service import create_group_invite_code as create_group_invite_code_service, join_group_by_invite_code as join_group_by_invite_code_service
from conftest import make_group as _make_group, make_invite_code as _make_invite_code, make_membership as _make_membership, make_user as _make_user
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


# --- CRUD -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_create_membership_persists_and_returns() -> None:
    group_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    db.add = MagicMock()

    membership = await create_membership_crud(db, group_id, user_id)

    assert isinstance(membership, Membership)
    assert membership.group_id == group_id
    assert membership.user_id == user_id
    assert membership.role == "member"
    db.add.assert_called_once_with(membership)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(membership)


@pytest.mark.asyncio
async def test_crud_get_invite_code_filters_on_hash() -> None:
    invite_code = _make_invite_code(uuid4())

    result = MagicMock()
    result.scalar_one_or_none.return_value = invite_code

    db = AsyncMock()
    db.execute.return_value = result

    found = await get_invite_code_by_hash_crud(db, "hash")

    assert found is invite_code

    statement = db.execute.call_args.args[0]
    compiled = str(statement).lower()
    assert "group_invite_codes.code_hash" in compiled


@pytest.mark.asyncio
async def test_crud_create_group_invite_code_persists_hash() -> None:
    group_id = uuid4()
    created_by_id = uuid4()

    db = AsyncMock()
    db.add = MagicMock()

    invite_code = await create_group_invite_code_crud(
        db, group_id, created_by_id, "deadbeef"
    )

    assert isinstance(invite_code, GroupInviteCode)
    assert invite_code.group_id == group_id
    assert invite_code.created_by_id == created_by_id
    assert invite_code.code_hash == "deadbeef"
    db.add.assert_called_once_with(invite_code)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(invite_code)


# --- Service: join --------------------------------------------------------


@pytest.mark.asyncio
async def test_service_join_raises_404_for_unknown_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_invite_code_by_hash_crud",
        AsyncMock(return_value=None),
    )

    joiner = _make_user("joiner")
    with pytest.raises(HTTPException) as exc_info:
        await join_group_by_invite_code_service(
            AsyncMock(), GroupJoinRequest(invite_code="nope"), joiner
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_service_join_raises_400_for_revoked_code(monkeypatch) -> None:
    invite_code = _make_invite_code(uuid4(), revoked_at=datetime.now(UTC))
    monkeypatch.setattr(
        "app.services.group_service.get_invite_code_by_hash_crud",
        AsyncMock(return_value=invite_code),
    )

    joiner = _make_user("joiner")
    with pytest.raises(HTTPException) as exc_info:
        await join_group_by_invite_code_service(
            AsyncMock(), GroupJoinRequest(invite_code="x"), joiner
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_service_join_raises_400_for_expired_code(monkeypatch) -> None:
    invite_code = _make_invite_code(
        uuid4(), expires_at=datetime.now(UTC) - timedelta(hours=1)
    )
    monkeypatch.setattr(
        "app.services.group_service.get_invite_code_by_hash_crud",
        AsyncMock(return_value=invite_code),
    )

    joiner = _make_user("joiner")
    with pytest.raises(HTTPException) as exc_info:
        await join_group_by_invite_code_service(
            AsyncMock(), GroupJoinRequest(invite_code="x"), joiner
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_service_join_raises_409_for_existing_member(monkeypatch) -> None:
    group_id = uuid4()
    invite_code = _make_invite_code(group_id)
    joiner = _make_user("joiner")

    monkeypatch.setattr(
        "app.services.group_service.get_invite_code_by_hash_crud",
        AsyncMock(return_value=invite_code),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=_make_membership(group_id, joiner.id)),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.create_membership_crud", create_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await join_group_by_invite_code_service(
            AsyncMock(), GroupJoinRequest(invite_code="x"), joiner
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_join_creates_membership_on_success(monkeypatch) -> None:
    group_id = uuid4()
    invite_code = _make_invite_code(group_id)
    joiner = _make_user("joiner")
    expected = _make_membership(group_id, joiner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_invite_code_by_hash_crud",
        AsyncMock(return_value=invite_code),
    )
    monkeypatch.setattr(
        "app.services.group_service.get_membership_crud",
        AsyncMock(return_value=None),
    )
    create_mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "app.services.group_service.create_membership_crud", create_mock
    )

    db = AsyncMock()
    result = await join_group_by_invite_code_service(
        db, GroupJoinRequest(invite_code="x"), joiner
    )

    assert result is expected
    create_mock.assert_awaited_once_with(
        db, group_id, joiner.id, role="member"
    )


# --- Service: create invite code ------------------------------------------


@pytest.mark.asyncio
async def test_service_create_code_raises_404_for_missing_group(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=None),
    )

    owner = _make_user("owner")
    with pytest.raises(HTTPException) as exc_info:
        await create_group_invite_code_service(AsyncMock(), uuid4(), owner)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_service_create_code_raises_403_for_non_owner(
    monkeypatch,
) -> None:
    group = _make_group(uuid4())
    requester = _make_user("not-owner")

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.group_service.create_group_invite_code_crud", create_mock
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_group_invite_code_service(AsyncMock(), group.id, requester)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_create_code_returns_raw_code_for_owner(
    monkeypatch,
) -> None:
    owner = _make_user("owner")
    group = _make_group(owner.id)

    monkeypatch.setattr(
        "app.services.group_service.get_group_by_id_crud",
        AsyncMock(return_value=group),
    )

    async def _fake_create(db, group_id, created_by_id, code_hash, expires_at=None):
        invite_code = _make_invite_code(group_id)
        invite_code.code_hash = code_hash
        return invite_code

    monkeypatch.setattr(
        "app.services.group_service.create_group_invite_code_crud",
        AsyncMock(side_effect=_fake_create),
    )

    result = await create_group_invite_code_service(
        AsyncMock(), group.id, owner
    )

    assert isinstance(result, GroupInviteCodeResponse)
    assert result.group_id == group.id
    assert result.invite_code
    assert result.expires_at is None


# --- Router ---------------------------------------------------------------


def test_join_group_endpoint_returns_serialized_membership(monkeypatch) -> None:
    joiner = _make_user("joiner")
    group_id = uuid4()
    membership = _make_membership(group_id, joiner.id)

    service_mock = AsyncMock(return_value=membership)
    monkeypatch.setattr(
        "app.routers.group_router.join_group_by_invite_code_service",
        service_mock,
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: joiner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post("/groups/join", json={"invite_code": "secret"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201

    body = response.json()
    assert body["id"] == str(membership.id)
    assert body["group_id"] == str(group_id)
    assert body["user_id"] == str(joiner.id)
    assert body["role"] == "member"

    service_mock.assert_awaited_once()
    _, awaited_request, awaited_user = service_mock.await_args.args
    assert awaited_request.invite_code == "secret"
    assert awaited_user is joiner


def test_join_group_endpoint_requires_invite_code() -> None:
    joiner = _make_user("joiner")

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: joiner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post("/groups/join", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_create_invite_code_endpoint_returns_raw_code(monkeypatch) -> None:
    owner = _make_user("owner")
    group_id = uuid4()

    payload = GroupInviteCodeResponse(
        group_id=group_id,
        invite_code="raw-secret",
        created_at=datetime.now(UTC),
        expires_at=None,
    )
    service_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(
        "app.routers.group_router.create_group_invite_code_service",
        service_mock,
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: owner
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post(f"/groups/{group_id}/invite-code")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201

    body = response.json()
    assert body["invite_code"] == "raw-secret"
    assert body["group_id"] == str(group_id)

    service_mock.assert_awaited_once()
    _, awaited_group_id, awaited_user = service_mock.await_args.args
    assert awaited_group_id == group_id
    assert awaited_user is owner


def test_join_routes_are_registered() -> None:
    group_paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/groups")
    }

    assert "/groups/join" in group_paths
    assert "/groups/{group_id}/invite-code" in group_paths
