"""Tests for password hashing, JWT helpers, and the auth dependency.

Covers :mod:`app.core.security` (bcrypt hashing and JWT encode/decode) and the
``get_current_user`` dependency in :mod:`app.dependencies.auth`, which is the
one place the whole suite otherwise stubs out. The dependency's database lookup
is mocked; no live database is touched.
"""

from uuid import uuid4

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.dependencies.auth import get_current_user
from conftest import make_user as _make_user
from fastapi import HTTPException, status
from unittest.mock import AsyncMock


# --- Password hashing -----------------------------------------------------


def test_password_hash_roundtrip_and_mismatch() -> None:
    hashed = get_password_hash("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_verify_password_returns_false_for_malformed_hash() -> None:
    # A non-bcrypt string must be treated as a clean non-match, not an error.
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


# --- JWT encode / decode --------------------------------------------------


def test_access_token_roundtrip_carries_subject() -> None:
    subject = str(uuid4())
    token = create_access_token(subject=subject)

    payload = decode_access_token(token)

    assert payload["sub"] == subject
    assert "exp" in payload
    assert "iat" in payload


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(subject=str(uuid4()))

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "tampered")


# --- get_current_user dependency ------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_401_for_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="not-a-jwt", db=AsyncMock())

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_401_when_sub_claim_missing() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"foo": "bar"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=AsyncMock())

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_401_when_sub_is_not_a_uuid() -> None:
    token = create_access_token(subject="not-a-uuid")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=AsyncMock())

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_401_when_user_not_found(monkeypatch) -> None:
    token = create_access_token(subject=str(uuid4()))
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_by_id",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=AsyncMock())

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_returns_resolved_user(monkeypatch) -> None:
    user = _make_user("member")
    token = create_access_token(subject=str(user.id))
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_by_id",
        AsyncMock(return_value=user),
    )

    result = await get_current_user(token=token, db=AsyncMock())

    assert result is user
