"""Background job that turns an uploaded image into a placed 3D mesh.

Scheduled via FastAPI ``BackgroundTasks`` after the upload request has already
returned ``202``, so the browser never waits on the GPU. The job:

1. Sends the source image to TRELLIS (Colab Gradio) and gets a ``.glb`` back.
2. Uploads the ``.glb`` to the Supabase mesh bucket.
3. Marks the submission ``ready`` and creates the ``MapObject``.

Any failure flips the submission to ``failed`` with an error message so the
polling frontend can surface it. TRELLIS and Supabase clients are synchronous,
so blocking calls are dispatched to a worker thread to avoid stalling the loop.
"""

import logging
import os
from uuid import UUID

from app.core.config import get_settings
from app.crud.generation_crud import (
    get_submission,
    mark_submission_failed,
    mark_submission_ready,
)
from app.db.database import AsyncSessionLocal
from app.services import storage, trellis
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


async def run_generation_job(submission_id: UUID, source_image_path: str) -> None:
    """Run the TRELLIS generation pipeline for a submission.

    Opens its own database session (the request-scoped session is already
    closed by the time a background task runs) and always removes the temporary
    source image file when finished.
    """
    settings = get_settings()
    try:
        async with AsyncSessionLocal() as db:
            submission = await get_submission(db, submission_id)
            if submission is None:
                logger.error("Generation job: submission %s not found", submission_id)
                return

            try:
                glb_path = await run_in_threadpool(
                    trellis.generate_mesh, source_image_path
                )

                key = storage.mesh_key(
                    submission.group_id, submission.pin_id, submission.id
                )
                await run_in_threadpool(
                    storage.upload_file,
                    settings.supabase_mesh_bucket,
                    key,
                    glb_path,
                    "model/gltf-binary",
                )
                public_url = await run_in_threadpool(
                    storage.get_public_url, settings.supabase_mesh_bucket, key
                )

                await mark_submission_ready(
                    db,
                    submission,
                    mesh_storage_key=key,
                    mesh_public_url=public_url,
                )
                logger.info("Generation job %s ready: %s", submission_id, public_url)
            except Exception as exc:  # noqa: BLE001 - persist failure for polling
                logger.exception("Generation job %s failed", submission_id)
                await mark_submission_failed(db, submission, error_message=str(exc))
    finally:
        try:
            os.remove(source_image_path)
        except OSError:
            logger.warning(
                "Generation job %s: could not remove temp file %s",
                submission_id,
                source_image_path,
            )
