"""Tests for the single-image 3D generation pipeline.

Covers the service-layer authorization/validation, the CRUD status
transitions, and the poll endpoint. TRELLIS and Supabase Storage are never
touched: storage uploads are mocked and the TRELLIS background task is only
scheduled (never executed) by ``BackgroundTasks``.
"""

import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.main import app
from app.models.group_model import Membership
from app.models.media_submission_model import (
    SUBMISSION_STATUS_FAILED,
    SUBMISSION_STATUS_PROCESSING,
    SUBMISSION_STATUS_READY,
    MediaSubmission,
)
from app.services import generation_service
from app.services.generation_service import (
    create_generation_submission,
    get_generation_submission,
    list_group_generations,
    list_pin_generations,
)
from conftest import make_group as _make_group, make_pin as _make_pin, make_user as _make_user
from fastapi import BackgroundTasks, HTTPException, status
from fastapi.testclient import TestClient


def _make_submission(group_id, pin_id, *, status_value: str) -> MediaSubmission:
    submission = MediaSubmission(
        group_id=group_id,
        pin_id=pin_id,
        user_id=uuid4(),
        source_image_key="k/source.jpg",
    )
    submission.id = uuid4()
    submission.status = status_value
    submission.created_at = datetime.now(UTC)
    return submission


def _pass_membership(monkeypatch, group) -> None:
    monkeypatch.setattr(
        generation_service, "get_group_by_id", AsyncMock(return_value=group)
    )
    membership = Membership(user_id=group.owner_id, group_id=group.id, role="owner")
    monkeypatch.setattr(
        generation_service, "get_membership_crud", AsyncMock(return_value=membership)
    )


@pytest.mark.asyncio
async def test_create_rejects_non_member(monkeypatch) -> None:
    user = _make_user("outsider")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        generation_service, "get_group_by_id", AsyncMock(return_value=group)
    )
    monkeypatch.setattr(
        generation_service, "get_membership_crud", AsyncMock(return_value=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_generation_submission(
            AsyncMock(),
            group.id,
            uuid4(),
            user,
            image_bytes=b"data",
            content_type="image/jpeg",
            background_tasks=BackgroundTasks(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_rejects_bad_content_type(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    with pytest.raises(HTTPException) as exc_info:
        await create_generation_submission(
            AsyncMock(),
            group.id,
            uuid4(),
            user,
            image_bytes=b"data",
            content_type="application/pdf",
            background_tasks=BackgroundTasks(),
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_rejects_missing_pin(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)
    monkeypatch.setattr(generation_service, "get_pin", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await create_generation_submission(
            AsyncMock(),
            group.id,
            uuid4(),
            user,
            image_bytes=b"data",
            content_type="image/jpeg",
            background_tasks=BackgroundTasks(),
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_schedules_generation(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    pin = _make_pin(group.id, user.id)
    _pass_membership(monkeypatch, group)
    monkeypatch.setattr(generation_service, "get_pin", AsyncMock(return_value=pin))

    async def _create_submission(_db, **kwargs):
        submission = _make_submission(
            kwargs["group_id"],
            kwargs["pin_id"],
            status_value=SUBMISSION_STATUS_PROCESSING,
        )
        submission.id = kwargs["submission_id"]
        return submission

    monkeypatch.setattr(generation_service, "create_submission", _create_submission)
    monkeypatch.setattr(generation_service.storage, "upload_bytes", MagicMock())

    background_tasks = BackgroundTasks()
    submission = await create_generation_submission(
        AsyncMock(),
        group.id,
        pin.id,
        user,
        image_bytes=b"imagedata",
        content_type="image/png",
        background_tasks=background_tasks,
    )

    assert submission.status == SUBMISSION_STATUS_PROCESSING
    # The TRELLIS job is scheduled to run after the response, not inline.
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_get_submission_scoped_to_group(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    other_group_submission = _make_submission(
        uuid4(), uuid4(), status_value=SUBMISSION_STATUS_PROCESSING
    )
    monkeypatch.setattr(
        generation_service,
        "get_submission",
        AsyncMock(return_value=other_group_submission),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_generation_submission(AsyncMock(), group.id, uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_pin_generations_returns_submissions(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    pin = _make_pin(group.id, user.id)
    _pass_membership(monkeypatch, group)
    monkeypatch.setattr(generation_service, "get_pin", AsyncMock(return_value=pin))

    submissions = [
        _make_submission(group.id, pin.id, status_value=SUBMISSION_STATUS_READY),
        _make_submission(group.id, pin.id, status_value=SUBMISSION_STATUS_PROCESSING),
    ]
    monkeypatch.setattr(
        generation_service,
        "list_submissions_for_pin",
        AsyncMock(return_value=submissions),
    )

    result = await list_pin_generations(AsyncMock(), group.id, pin.id, user)

    assert result == submissions


@pytest.mark.asyncio
async def test_list_pin_generations_rejects_missing_pin(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)
    monkeypatch.setattr(generation_service, "get_pin", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await list_pin_generations(AsyncMock(), group.id, uuid4(), user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_list_group_generations_rejects_non_member(monkeypatch) -> None:
    user = _make_user("outsider")
    group = _make_group(uuid4())

    monkeypatch.setattr(
        generation_service, "get_group_by_id", AsyncMock(return_value=group)
    )
    monkeypatch.setattr(
        generation_service, "get_membership_crud", AsyncMock(return_value=None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await list_group_generations(AsyncMock(), group.id, user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_group_generations_returns_submissions(monkeypatch) -> None:
    user = _make_user("member")
    group = _make_group(user.id)
    _pass_membership(monkeypatch, group)

    submissions = [
        _make_submission(group.id, uuid4(), status_value=SUBMISSION_STATUS_READY),
    ]
    monkeypatch.setattr(
        generation_service,
        "list_submissions_for_group",
        AsyncMock(return_value=submissions),
    )

    result = await list_group_generations(AsyncMock(), group.id, user)

    assert result == submissions


@pytest.mark.asyncio
async def test_mark_submission_ready_creates_map_object(monkeypatch) -> None:
    from app.crud import generation_crud

    group_id = uuid4()
    pin = _make_pin(group_id, uuid4())
    submission = _make_submission(
        group_id, pin.id, status_value=SUBMISSION_STATUS_PROCESSING
    )

    monkeypatch.setattr(generation_crud, "get_pin", AsyncMock(return_value=pin))

    db = AsyncMock()
    db.add = MagicMock()
    map_object = await generation_crud.mark_submission_ready(
        db,
        submission,
        mesh_storage_key="meshes/model.glb",
        mesh_public_url="https://cdn/model.glb",
    )

    assert submission.status == SUBMISSION_STATUS_READY
    assert submission.mesh_public_url == "https://cdn/model.glb"
    assert map_object.mesh_public_url == "https://cdn/model.glb"
    assert map_object.lat == pin.lat
    assert map_object.lng == pin.lng
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_submission_failed_records_error() -> None:
    from app.crud import generation_crud

    submission = _make_submission(
        uuid4(), uuid4(), status_value=SUBMISSION_STATUS_PROCESSING
    )

    db = AsyncMock()
    result = await generation_crud.mark_submission_failed(
        db, submission, error_message="Colab notebook is asleep"
    )

    assert result.status == SUBMISSION_STATUS_FAILED
    assert result.error_message == "Colab notebook is asleep"
    db.commit.assert_awaited_once()


def _session_factory_yielding(db) -> MagicMock:
    """Build a mock ``AsyncSessionLocal`` whose context manager yields ``db``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    return factory


@pytest.mark.asyncio
async def test_run_generation_job_marks_ready(monkeypatch) -> None:
    from app.services import generation

    submission = _make_submission(
        uuid4(), uuid4(), status_value=SUBMISSION_STATUS_PROCESSING
    )

    monkeypatch.setattr(
        generation, "AsyncSessionLocal", _session_factory_yielding(AsyncMock())
    )
    monkeypatch.setattr(
        generation, "get_submission", AsyncMock(return_value=submission)
    )
    monkeypatch.setattr(
        generation.trellis, "generate_mesh", MagicMock(return_value="/tmp/model.glb")
    )
    monkeypatch.setattr(generation.storage, "upload_file", MagicMock())
    monkeypatch.setattr(
        generation.storage,
        "get_public_url",
        MagicMock(return_value="https://cdn/model.glb"),
    )
    ready_mock = AsyncMock()
    failed_mock = AsyncMock()
    monkeypatch.setattr(generation, "mark_submission_ready", ready_mock)
    monkeypatch.setattr(generation, "mark_submission_failed", failed_mock)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    await generation.run_generation_job(submission.id, temp_path)

    ready_mock.assert_awaited_once()
    failed_mock.assert_not_awaited()
    # The temp source image is always cleaned up.
    assert not os.path.exists(temp_path)


@pytest.mark.asyncio
async def test_run_generation_job_marks_failed_on_trellis_error(monkeypatch) -> None:
    from app.services import generation

    submission = _make_submission(
        uuid4(), uuid4(), status_value=SUBMISSION_STATUS_PROCESSING
    )

    monkeypatch.setattr(
        generation, "AsyncSessionLocal", _session_factory_yielding(AsyncMock())
    )
    monkeypatch.setattr(
        generation, "get_submission", AsyncMock(return_value=submission)
    )
    monkeypatch.setattr(
        generation.trellis,
        "generate_mesh",
        MagicMock(side_effect=RuntimeError("Colab notebook is asleep")),
    )
    ready_mock = AsyncMock()
    failed_mock = AsyncMock()
    monkeypatch.setattr(generation, "mark_submission_ready", ready_mock)
    monkeypatch.setattr(generation, "mark_submission_failed", failed_mock)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_path = temp_file.name

    await generation.run_generation_job(submission.id, temp_path)

    failed_mock.assert_awaited_once()
    ready_mock.assert_not_awaited()
    assert not os.path.exists(temp_path)


def test_get_generation_endpoint_returns_status(monkeypatch) -> None:
    requester = _make_user("requester")
    group_id = uuid4()
    submission = _make_submission(
        group_id, uuid4(), status_value=SUBMISSION_STATUS_READY
    )
    submission.mesh_public_url = "https://cdn/model.glb"

    service_mock = AsyncMock(return_value=submission)
    monkeypatch.setattr(
        "app.routers.map_router.get_generation_submission_service", service_mock
    )

    async def _override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_authenticated_user] = lambda: requester
    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        response = client.get(f"/groups/{group_id}/generations/{submission.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SUBMISSION_STATUS_READY
    assert body["mesh_url"] == "https://cdn/model.glb"


def test_generation_routes_are_registered() -> None:
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/groups/{group_id}/pins/{pin_id}/generations" in paths
    assert "/groups/{group_id}/generations" in paths
    assert "/groups/{group_id}/generations/{generation_id}" in paths
