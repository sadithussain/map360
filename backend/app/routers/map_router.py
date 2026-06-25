"""HTTP routes for group map state."""

from uuid import UUID

from app.db.database import get_db
from app.dependencies.auth import get_current_user as get_authenticated_user
from app.models.user_model import User
from app.schemas.map_schema import MapStateResponse
from app.services.map_service import get_map_state as get_map_state_service
from fastapi import APIRouter, Depends, status
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
