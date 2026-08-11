"""Tests for user accounts (registration, login, profile, password change).

Covers the three layers of the user flow:

* CRUD: ``create_user`` persists a hashed password and commits;
  ``update_user_password`` writes a new hash and commits.
* Service: ``register_user`` validates fields, hashes the password, and maps a
  unique-constraint violation to ``409``; ``authenticate_user`` returns a token
  on success and ``401`` for unknown emails or wrong passwords;
  ``change_user_password`` requires the correct current password;
  ``check_email_exists`` / ``check_username_exists`` delegate to CRUD.
* Router: register/login/``/me``/exists/password endpoints serialize correctly
  and never leak credentials.

These tests deliberately avoid a live database: CRUD is exercised with a mocked
``AsyncSession`` and the router with FastAPI dependency overrides.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.core.security import get_password_hash
from app.crud.user_crud import create_user as create_user_crud
from app.crud.user_crud import update_user_password as update_user_password_crud
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.user_model import User
from app.schemas.user_schema import (
    Token,
    UserCreate,
    UserLogin,
    UserPasswordChange,
)
from app.services.user_service import (
    authenticate_user,
    change_user_password,
    check_email_exists,
    check_username_exists,
    register_user,
)
from conftest import make_user as _make_user
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


# --- CRUD -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_crud_create_user_persists_hashed_password() -> None:
    db = AsyncMock()
    db.add = MagicMock()

    payload = UserCreate(
        username="newbie", email="newbie@example.com", password="password123"
    )

    user = await create_user_crud(db, payload, "hashed-value")

    assert isinstance(user, User)
    assert user.username == "newbie"
    assert user.email == "newbie@example.com"
    assert user.hashed_password == "hashed-value"
    # The raw password must never be persisted.
    assert not hasattr(user, "password")
    db.add.assert_called_once_with(user)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_crud_update_user_password_writes_new_hash() -> None:
    db = AsyncMock()
    db.add = MagicMock()

    user = _make_user("changer")
    user.hashed_password = "old-hash"

    updated = await update_user_password_crud(db, user, "new-hash")

    assert updated.hashed_password == "new-hash"
    db.add.assert_called_once_with(user)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


# --- Service: register ----------------------------------------------------


@pytest.mark.asyncio
async def test_service_register_rejects_short_username(monkeypatch) -> None:
    create_mock = AsyncMock()
    monkeypatch.setattr("app.services.user_service.create_user", create_mock)

    # Pydantic normally blocks this at the HTTP boundary; ``model_construct``
    # skips schema validation so the service's own guard is exercised directly.
    payload = UserCreate.model_construct(
        username="ab", email="a@example.com", password="password123"
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_user(AsyncMock(), payload)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_register_hashes_password_and_persists(monkeypatch) -> None:
    stored = _make_user("newbie")
    create_mock = AsyncMock(return_value=stored)
    monkeypatch.setattr("app.services.user_service.create_user", create_mock)

    payload = UserCreate(
        username="newbie", email="newbie@example.com", password="password123"
    )

    result = await register_user(AsyncMock(), payload)

    assert result is stored
    create_mock.assert_awaited_once()
    _, awaited_payload, awaited_hash = create_mock.await_args.args
    assert awaited_payload is payload
    # The service must hash before persisting, never pass the raw password.
    assert awaited_hash != "password123"
    assert awaited_hash


@pytest.mark.asyncio
async def test_service_register_maps_integrity_error_to_409(monkeypatch) -> None:
    def _raise_integrity(*_args, **_kwargs):
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    monkeypatch.setattr(
        "app.services.user_service.create_user",
        AsyncMock(side_effect=_raise_integrity),
    )

    payload = UserCreate(
        username="dupe", email="dupe@example.com", password="password123"
    )

    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await register_user(db, payload)

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    db.rollback.assert_awaited_once()


# --- Service: authenticate ------------------------------------------------


@pytest.mark.asyncio
async def test_service_authenticate_returns_token_on_success(monkeypatch) -> None:
    user = _make_user("member")
    user.hashed_password = get_password_hash("password123")

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        AsyncMock(return_value=user),
    )

    credentials = UserLogin(email=user.email, password="password123")
    token = await authenticate_user(AsyncMock(), credentials)

    assert isinstance(token, Token)
    assert token.access_token
    assert token.token_type == "bearer"


@pytest.mark.asyncio
async def test_service_authenticate_401_for_unknown_email(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        AsyncMock(return_value=None),
    )

    credentials = UserLogin(email="ghost@example.com", password="password123")
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(AsyncMock(), credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_service_authenticate_401_for_wrong_password(monkeypatch) -> None:
    user = _make_user("member")
    user.hashed_password = get_password_hash("right-password")

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email",
        AsyncMock(return_value=user),
    )

    credentials = UserLogin(email=user.email, password="wrong-password")
    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user(AsyncMock(), credentials)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# --- Service: change password ---------------------------------------------


@pytest.mark.asyncio
async def test_service_change_password_401_for_wrong_current(monkeypatch) -> None:
    user = _make_user("member")
    user.hashed_password = get_password_hash("old-password")

    update_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.user_service.update_user_password_crud", update_mock
    )

    passwords = UserPasswordChange(
        current_password="not-the-old-one", new_password="new-password"
    )
    with pytest.raises(HTTPException) as exc_info:
        await change_user_password(AsyncMock(), user, passwords)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    update_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_change_password_persists_new_hash(monkeypatch) -> None:
    user = _make_user("member")
    user.hashed_password = get_password_hash("old-password")

    update_mock = AsyncMock(return_value=user)
    monkeypatch.setattr(
        "app.services.user_service.update_user_password_crud", update_mock
    )

    passwords = UserPasswordChange(
        current_password="old-password", new_password="brand-new-password"
    )
    db = AsyncMock()
    result = await change_user_password(db, user, passwords)

    assert result is user
    update_mock.assert_awaited_once()
    awaited_db, awaited_user, awaited_hash = update_mock.await_args.args
    assert awaited_db is db
    assert awaited_user is user
    assert awaited_hash != "brand-new-password"


# --- Service: existence checks --------------------------------------------


@pytest.mark.asyncio
async def test_service_check_email_exists_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email_crud",
        AsyncMock(return_value=_make_user("taken")),
    )
    assert await check_email_exists(AsyncMock(), "taken@example.com") is True

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_email_crud",
        AsyncMock(return_value=None),
    )
    assert await check_email_exists(AsyncMock(), "free@example.com") is False


@pytest.mark.asyncio
async def test_service_check_username_exists_delegates(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.user_service.get_user_by_username_crud",
        AsyncMock(return_value=_make_user("taken")),
    )
    assert await check_username_exists(AsyncMock(), "taken") is True

    monkeypatch.setattr(
        "app.services.user_service.get_user_by_username_crud",
        AsyncMock(return_value=None),
    )
    assert await check_username_exists(AsyncMock(), "free") is False


# --- Router ---------------------------------------------------------------


def test_register_endpoint_returns_created_user_without_credentials(
    monkeypatch,
) -> None:
    created = _make_user("newbie")
    service_mock = AsyncMock(return_value=created)
    monkeypatch.setattr(
        "app.routers.user_router.register_user_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/users/register",
            json={
                "username": "newbie",
                "email": "newbie@example.com",
                "password": "password123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newbie"
    assert body["email"] == "newbie@example.com"
    assert "password" not in body
    assert "hashed_password" not in body
    service_mock.assert_awaited_once()


def test_login_endpoint_returns_token(monkeypatch) -> None:
    service_mock = AsyncMock(return_value=Token(access_token="signed-jwt"))
    monkeypatch.setattr(
        "app.routers.user_router.authenticate_user", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/users/login",
            json={"email": "member@example.com", "password": "password123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "signed-jwt"
    assert body["token_type"] == "bearer"
    service_mock.assert_awaited_once()


def test_me_endpoint_returns_authenticated_user() -> None:
    requester = _make_user("member")

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get("/users/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "member"
    assert body["id"] == str(requester.id)
    assert "hashed_password" not in body


def test_exists_email_endpoint_reports_availability(monkeypatch) -> None:
    service_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.routers.user_router.check_email_exists_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get("/users/exists/email/taken@example.com")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() is True
    service_mock.assert_awaited_once()


def test_change_password_endpoint_returns_204(monkeypatch) -> None:
    requester = _make_user("me")

    service_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.routers.user_router.change_user_password_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.put(
            "/users/me/password",
            json={
                "current_password": "old-password",
                "new_password": "brand-new-password",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    service_mock.assert_awaited_once()
    _, awaited_user, awaited_passwords = service_mock.await_args.args
    assert awaited_user is requester
    assert awaited_passwords.new_password == "brand-new-password"


def test_user_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/users/register" in paths
    assert "/users/login" in paths
    assert "/users/me" in paths
    assert "/users/me/password" in paths
    assert "/users/exists/email/{email}" in paths
    assert "/users/exists/username/{username}" in paths
