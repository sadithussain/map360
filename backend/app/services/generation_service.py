"""Business logic for the single-image 3D generation pipeline.

Handles authorization, source-image upload, submission creation, and scheduling
the TRELLIS background job. Routers depend on this module rather than touching
CRUD or storage directly.
"""

import tempfile
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.crud.generation_crud import (
    create_submission,
    get_pin,
    get_submission,
    list_submissions_for_group,
    list_submissions_for_pin,
)
from app.crud.group_crud import get_membership as get_membership_crud
from app.models.media_submission_model import MediaSubmission
from app.models.user_model import User
from app.services import storage
from app.services.generation import run_generation_job
from app.services.group_service import get_group_by_id
from fastapi import BackgroundTasks, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

# Accepted source-image content types mapped to a storage file extension.
_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Matches the frontend's 10 MB per-image cap.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def _require_group_membership(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> None:
    """Raise 404 if the group is missing, 403 if the user is not a member."""
    await get_group_by_id(db, group_id)

    membership = await get_membership_crud(db, group_id, current_user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )


async def create_generation_submission(
    db: AsyncSession,
    group_id: UUID,
    pin_id: UUID,
    current_user: User,
    *,
    image_bytes: bytes,
    content_type: str | None,
    background_tasks: BackgroundTasks,
) -> MediaSubmission:
    """Accept one photo, start a submission, and schedule TRELLIS generation.

    Validates membership, the pin, and the image; uploads the source photo to
    Supabase Storage; records a ``processing`` submission; and schedules the
    background job. Returns immediately so the caller can respond ``202``.
    """
    await _require_group_membership(db, group_id, current_user)

    extension = _ALLOWED_IMAGE_TYPES.get((content_type or "").lower())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be JPEG, PNG, or WebP.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded image is empty.",
        )
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be 10 MB or smaller.",
        )

    pin = await get_pin(db, pin_id)
    if pin is None or pin.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location pin not found in this group.",
        )

    settings = get_settings()

    submission_id = uuid4()
    source_key = storage.source_image_key(group_id, pin_id, submission_id, extension)
    submission = await create_submission(
        db,
        submission_id=submission_id,
        group_id=group_id,
        pin_id=pin_id,
        user_id=current_user.id,
        source_image_key=source_key,
    )

    await run_in_threadpool(
        storage.upload_bytes,
        settings.supabase_media_bucket,
        source_key,
        image_bytes,
        content_type,
    )

    await db.commit()
    await db.refresh(submission)

    # Persist the source image to a temp file for the Gradio client to upload,
    # then hand generation off to a background task (no GPU wait on this request).
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        temp_file.write(image_bytes)
        temp_path = temp_file.name

    background_tasks.add_task(run_generation_job, submission.id, temp_path)

    return submission


async def get_generation_submission(
    db: AsyncSession,
    group_id: UUID,
    submission_id: UUID,
    current_user: User,
) -> MediaSubmission:
    """Return a submission for polling, enforcing group membership and scope."""
    await _require_group_membership(db, group_id, current_user)

    submission = await get_submission(db, submission_id)
    if submission is None or submission.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found in this group.",
        )

    return submission


async def list_pin_generations(
    db: AsyncSession,
    group_id: UUID,
    pin_id: UUID,
    current_user: User,
) -> list[MediaSubmission]:
    """List all submissions for a pin, enforcing group membership and scope."""
    await _require_group_membership(db, group_id, current_user)

    pin = await get_pin(db, pin_id)
    if pin is None or pin.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location pin not found in this group.",
        )

    return await list_submissions_for_pin(db, group_id, pin_id)


async def list_group_generations(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> list[MediaSubmission]:
    """List all submissions for a group, enforcing group membership."""
    await _require_group_membership(db, group_id, current_user)

    return await list_submissions_for_group(db, group_id)
