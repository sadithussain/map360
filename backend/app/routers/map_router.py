"""HTTP routes for group map state."""

from uuid import UUID

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.map_schema import (
    LocationPinCreate,
    LocationPinResponse,
    MapObjectResponse,
    MapStateResponse,
    SubmissionResponse,
)
from app.services.generation_service import (
    create_generation_submission as create_generation_submission_service,
)
from app.services.generation_service import (
    get_generation_submission as get_generation_submission_service,
)
from app.services.generation_service import (
    list_group_generations as list_group_generations_service,
)
from app.services.generation_service import (
    list_pin_generations as list_pin_generations_service,
)
from app.services.map_service import create_location_pin as create_location_pin_service
from app.services.map_service import delete_location_pin as delete_location_pin_service
from app.services.map_service import get_map_object as get_map_object_service
from app.services.map_service import get_map_state as get_map_state_service
from app.services.map_service import list_map_objects as list_map_objects_service
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["maps"])


@router.get(
    "/groups/{group_id}/map-state",
    response_model=MapStateResponse,
    status_code=status.HTTP_200_OK,
)
async def get_map_state(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> MapStateResponse:
    """Return the map state for a group the authenticated user belongs to."""
    return await get_map_state_service(db, group_id, current_user)


@router.get(
    "/groups/{group_id}/map-objects",
    response_model=list[MapObjectResponse],
    status_code=status.HTTP_200_OK,
)
async def list_map_objects(
    group_id: UUID,
    min_lng: float | None = Query(default=None, ge=-180, le=180),
    min_lat: float | None = Query(default=None, ge=-90, le=90),
    max_lng: float | None = Query(default=None, ge=-180, le=180),
    max_lat: float | None = Query(default=None, ge=-90, le=90),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[MapObjectResponse]:
    """List a group's generated map objects, optionally within a lng/lat bbox.

    All four bbox params must be supplied together, or none of them.
    """
    bbox_values = (min_lng, min_lat, max_lng, max_lat)
    provided = [value is not None for value in bbox_values]
    if any(provided) and not all(provided):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide all of min_lng, min_lat, max_lng, max_lat, or none.",
        )

    bbox = bbox_values if all(provided) else None
    return await list_map_objects_service(db, group_id, current_user, bbox=bbox)


@router.get(
    "/groups/{group_id}/map-objects/{object_id}",
    response_model=MapObjectResponse,
    status_code=status.HTTP_200_OK,
)
async def get_map_object(
    group_id: UUID,
    object_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> MapObjectResponse:
    """Return a single map object with its mesh URL, scoped to the group."""
    return await get_map_object_service(db, group_id, object_id, current_user)


@router.post(
    "/groups/{group_id}/pins",
    response_model=LocationPinResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location_pin(
    group_id: UUID,
    payload: LocationPinCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> LocationPinResponse:
    """Create a location pin from a selected base-map building."""
    return await create_location_pin_service(db, group_id, current_user, payload)


@router.delete(
    "/groups/{group_id}/pins/{pin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_location_pin(
    group_id: UUID,
    pin_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a location pin and its submissions/objects from a group."""
    await delete_location_pin_service(db, group_id, pin_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/groups/{group_id}/pins/{pin_id}/generations",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation(
    group_id: UUID,
    pin_id: UUID,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    """Accept a single photo and start async TRELLIS mesh generation.

    Returns ``202`` immediately with a ``processing`` submission; the mesh is
    produced by a background task. Poll ``GET .../generations/{id}`` for status.
    """
    image_bytes = await image.read()
    submission = await create_generation_submission_service(
        db,
        group_id,
        pin_id,
        current_user,
        image_bytes=image_bytes,
        content_type=image.content_type,
        background_tasks=background_tasks,
    )
    return SubmissionResponse.model_validate(submission)


@router.get(
    "/groups/{group_id}/pins/{pin_id}/generations",
    response_model=list[SubmissionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_pin_generations(
    group_id: UUID,
    pin_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionResponse]:
    """List all generation submissions for a pin, newest first."""
    submissions = await list_pin_generations_service(
        db, group_id, pin_id, current_user
    )
    return [SubmissionResponse.model_validate(s) for s in submissions]


@router.get(
    "/groups/{group_id}/generations",
    response_model=list[SubmissionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_group_generations(
    group_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionResponse]:
    """List all generation submissions for a group, newest first."""
    submissions = await list_group_generations_service(db, group_id, current_user)
    return [SubmissionResponse.model_validate(s) for s in submissions]


@router.get(
    "/groups/{group_id}/generations/{generation_id}",
    response_model=SubmissionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_generation(
    group_id: UUID,
    generation_id: UUID,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    """Return the current status of a generation submission (poll target)."""
    submission = await get_generation_submission_service(
        db, group_id, generation_id, current_user
    )
    return SubmissionResponse.model_validate(submission)
