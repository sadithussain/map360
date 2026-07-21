"""Supabase Storage helper for source images and generated meshes.

The official ``supabase`` Python client is synchronous, so these functions are
plain (sync) callables. From the async request path call them via
``fastapi.concurrency.run_in_threadpool``; the background generation task runs
in a worker thread and can call them directly.

Two buckets are used: ``SUPABASE_MEDIA_BUCKET`` for uploaded source photos and
``SUPABASE_MESH_BUCKET`` for the generated ``.glb`` files.
"""

from functools import lru_cache
from uuid import UUID

from app.core.config import get_settings
from supabase import Client, create_client


class StorageConfigError(RuntimeError):
    """Raised when Supabase Storage credentials are not configured."""


class StorageError(RuntimeError):
    """Raised when a Supabase Storage operation fails."""


@lru_cache
def get_supabase_client() -> Client:
    """Return a cached service-role Supabase client.

    Raises ``StorageConfigError`` when the URL or service-role key is missing,
    which surfaces a clear message instead of a vague client error.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise StorageConfigError(
            "Supabase Storage is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY."
        )
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def source_image_key(
    group_id: UUID,
    pin_id: UUID,
    submission_id: UUID,
    extension: str,
) -> str:
    """Build the storage key for an uploaded source image."""
    ext = extension if extension.startswith(".") else f".{extension}"
    return f"{group_id}/{pin_id}/{submission_id}/source{ext}"


def mesh_key(group_id: UUID, pin_id: UUID, submission_id: UUID) -> str:
    """Build the storage key for a generated ``.glb`` mesh."""
    return f"{group_id}/{pin_id}/{submission_id}/model.glb"


def upload_bytes(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str,
) -> None:
    """Upload raw bytes to a bucket, overwriting any existing object."""
    client = get_supabase_client()
    try:
        client.storage.from_(bucket).upload(
            path=key,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001 - normalize client errors
        raise StorageError(f"Failed to upload to {bucket}/{key}: {exc}") from exc


def upload_file(bucket: str, key: str, file_path: str, content_type: str) -> None:
    """Upload a local file (e.g. the ``.glb`` returned by TRELLIS) to a bucket."""
    with open(file_path, "rb") as handle:
        upload_bytes(bucket, key, handle.read(), content_type)


def get_public_url(bucket: str, key: str) -> str:
    """Return the public URL for an object in a bucket."""
    client = get_supabase_client()
    try:
        return client.storage.from_(bucket).get_public_url(key)
    except Exception as exc:  # noqa: BLE001 - normalize client errors
        raise StorageError(
            f"Failed to resolve public URL for {bucket}/{key}: {exc}"
        ) from exc
